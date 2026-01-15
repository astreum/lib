import socket
from enum import IntEnum
from typing import List, Tuple, TYPE_CHECKING

from ..outgoing_queue import enqueue_outgoing
from ..models.message import Message, MessageTopic
from ...storage.models.atom import Atom
from ...storage.requests import get_atom_req_payload

if TYPE_CHECKING:
    from .. import Node
    from ..models.peer import Peer


class ObjectResponseType(IntEnum):
    OBJECT_FOUND = 0
    OBJECT_PROVIDER = 1
    OBJECT_NEAREST_PEER = 2


OBJECT_FOUND_ATOM_PAYLOAD = 1
OBJECT_FOUND_LIST_PAYLOAD = 2


class ObjectResponse:
    type: ObjectResponseType
    data: bytes
    atom_id: bytes

    def __init__(self, type: ObjectResponseType, data: bytes, atom_id: bytes = None):
        self.type = type
        self.data = data
        self.atom_id = atom_id

    def to_bytes(self):
        return bytes([self.type.value]) + self.atom_id + self.data

    @classmethod
    def from_bytes(cls, data: bytes) -> "ObjectResponse":
        # need at least 1 byte for type + 32 bytes for atom id
        if len(data) < 1 + 32:
            raise ValueError(f"Too short to be a valid ObjectResponse ({len(data)} bytes)")

        type_val = data[0]
        try:
            resp_type = ObjectResponseType(type_val)
        except ValueError:
            raise ValueError(f"Unknown ObjectResponseType: {type_val}")

        atom_id = data[1:33]
        payload   = data[33:]
        return cls(resp_type, payload, atom_id)


def encode_object_found_atom_payload(atom: Atom) -> bytes:
    return bytes([OBJECT_FOUND_ATOM_PAYLOAD]) + atom.to_bytes()


def encode_object_found_list_payload(atoms: List[Atom]) -> bytes:
    parts = [bytes([OBJECT_FOUND_LIST_PAYLOAD])]
    for atom in atoms:
        atom_bytes = atom.to_bytes()
        parts.append(len(atom_bytes).to_bytes(4, "big", signed=False))
        parts.append(atom_bytes)
    return b"".join(parts)


def decode_object_found_list_payload(payload: bytes) -> List[Atom]:
    atoms: List[Atom] = []
    offset = 0
    while offset < len(payload):
        if len(payload) - offset < 4:
            raise ValueError("truncated atom length")
        atom_len = int.from_bytes(payload[offset : offset + 4], "big", signed=False)
        offset += 4
        if atom_len <= 0:
            raise ValueError("invalid atom length")
        end = offset + atom_len
        if end > len(payload):
            raise ValueError("truncated atom payload")
        atoms.append(Atom.from_bytes(payload[offset:end]))
        offset = end
    return atoms


def decode_object_provider(payload: bytes) -> Tuple[bytes, str, int]:
    expected_len = 32 + 4 + 2
    if len(payload) < expected_len:
        raise ValueError("provider payload too short")

    provider_public_key = payload[:32]
    provider_ip_bytes = payload[32:36]
    provider_port_bytes = payload[36:38]

    provider_address = socket.inet_ntoa(provider_ip_bytes)
    provider_port = int.from_bytes(provider_port_bytes, byteorder="big", signed=False)
    return provider_public_key, provider_address, provider_port


def handle_object_response(node: "Node", peer: "Peer", message: Message) -> None:
    if message.content is None:
        node.logger.warning("OBJECT_RESPONSE from %s missing content", peer.address)
        return

    try:
        object_response = ObjectResponse.from_bytes(message.content)
    except Exception as exc:
        node.logger.warning("Error decoding OBJECT_RESPONSE from %s: %s", peer.address, exc)
        return

    if not node.has_atom_req(object_response.atom_id):
        return

    match object_response.type:
        case ObjectResponseType.OBJECT_FOUND:
            payload = object_response.data
            if not payload:
                node.logger.warning(
                    "OBJECT_FOUND payload for %s missing content",
                    object_response.atom_id.hex(),
                )
                return

            payload_type = payload[0]
            body = payload[1:]

            if payload_type == OBJECT_FOUND_ATOM_PAYLOAD:
                try:
                    atom = Atom.from_bytes(body)
                except Exception as exc:
                    node.logger.warning(
                        "Invalid OBJECT_FOUND atom payload for %s: %s",
                        object_response.atom_id.hex(),
                        exc,
                    )
                    return

                atom_id = atom.object_id()
                if object_response.atom_id != atom_id:
                    node.logger.warning(
                        "OBJECT_FOUND atom ID mismatch (expected=%s got=%s)",
                        object_response.atom_id.hex(),
                        atom_id.hex(),
                    )
                    return

                node.pop_atom_req(atom_id)
                node._hot_storage_set(atom_id, atom)
                return

            if payload_type == OBJECT_FOUND_LIST_PAYLOAD:
                try:
                    atoms = decode_object_found_list_payload(body)
                except Exception as exc:
                    node.logger.warning(
                        "Invalid OBJECT_FOUND list payload for %s: %s",
                        object_response.atom_id.hex(),
                        exc,
                    )
                    return

                if not atoms:
                    node.logger.warning(
                        "OBJECT_FOUND list payload for %s contained no atoms",
                        object_response.atom_id.hex(),
                    )
                    return

                node.logger.debug(
                    "OBJECT_FOUND list response atom_id=%s atoms=%s",
                    object_response.atom_id.hex(),
                    len(atoms),
                )
                root_id = atoms[0].object_id()
                if object_response.atom_id != root_id:
                    node.logger.warning(
                        "OBJECT_FOUND list root ID mismatch (expected=%s got=%s)",
                        object_response.atom_id.hex(),
                        root_id.hex(),
                    )
                    return

                node.pop_atom_req(root_id)
                for atom in atoms:
                    node._hot_storage_set(atom.object_id(), atom)
                return

            node.logger.warning(
                "Unknown OBJECT_FOUND payload type %s for %s",
                payload_type,
                object_response.atom_id.hex(),
            )

        case ObjectResponseType.OBJECT_PROVIDER:
            try:
                provider_key_bytes, provider_address, provider_port = decode_object_provider(object_response.data)
            except Exception as exc:
                node.logger.warning("Invalid OBJECT_PROVIDER payload from %s: %s", peer.address, exc)
                return

            from .object_request import ObjectRequest, ObjectRequestType
            from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

            payload_type = get_atom_req_payload(node, object_response.atom_id)
            if payload_type is None:
                payload_type = OBJECT_FOUND_ATOM_PAYLOAD

            try:
                provider_public_key = X25519PublicKey.from_public_bytes(provider_key_bytes)
                shared_key_bytes = node.relay_secret_key.exchange(provider_public_key)
            except Exception as exc:
                node.logger.warning(
                    "Unable to derive provider shared key for %s:%s: %s",
                    provider_address,
                    provider_port,
                    exc,
                )
                return

            obj_req = ObjectRequest(
                type=ObjectRequestType.OBJECT_GET,
                data=b"",
                atom_id=object_response.atom_id,
                payload_type=payload_type,
            )
            obj_req_bytes = obj_req.to_bytes()
            obj_req_msg = Message(
                topic=MessageTopic.OBJECT_REQUEST,
                body=obj_req_bytes,
                sender=node.relay_public_key,
            )
            obj_req_msg.encrypt(shared_key_bytes)
            enqueue_outgoing(
                node,
                (provider_address, provider_port),
                message=obj_req_msg,
                difficulty=1,
            )

        case ObjectResponseType.OBJECT_NEAREST_PEER:
            node.logger.debug("Ignoring OBJECT_NEAREST_PEER response from %s", peer.address)
