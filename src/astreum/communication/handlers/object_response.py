import socket
from enum import IntEnum
from typing import Tuple, TYPE_CHECKING

from ..models.message import Message, MessageTopic
from ...storage.models.atom import Atom

if TYPE_CHECKING:
    from .. import Node
    from ..models.peer import Peer


class ObjectResponseType(IntEnum):
    OBJECT_FOUND = 0
    OBJECT_PROVIDER = 1
    OBJECT_NEAREST_PEER = 2


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
            atom = Atom.from_bytes(object_response.data)
            atom_id = atom.object_id()
            if object_response.atom_id == atom_id:
                node.pop_atom_req(atom_id)
                node._hot_storage_set(atom_id, atom)
            else:
                node.logger.warning(
                    "OBJECT_FOUND atom ID mismatch (expected=%s got=%s)",
                    object_response.atom_id.hex(),
                    atom_id.hex(),
                )

        case ObjectResponseType.OBJECT_PROVIDER:
            try:
                _, provider_address, provider_port = decode_object_provider(object_response.data)
            except Exception as exc:
                node.logger.warning("Invalid OBJECT_PROVIDER payload from %s: %s", peer.address, exc)
                return

            from .object_request import ObjectRequest, ObjectRequestType

            obj_req = ObjectRequest(
                type=ObjectRequestType.OBJECT_GET,
                data=b"",
                atom_id=object_response.atom_id,
            )
            obj_req_bytes = obj_req.to_bytes()
            obj_req_msg = Message(
                topic=MessageTopic.OBJECT_REQUEST,
                body=obj_req_bytes,
                sender=node.relay_public_key,
            )
            obj_req_msg.encrypt(peer.shared_key_bytes)
            node.outgoing_queue.put((obj_req_msg.to_bytes(), (provider_address, provider_port)))

        case ObjectResponseType.OBJECT_NEAREST_PEER:
            node.logger.debug("Ignoring OBJECT_NEAREST_PEER response from %s", peer.address)
