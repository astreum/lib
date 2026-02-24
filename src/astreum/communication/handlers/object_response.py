import socket
from enum import IntEnum
from typing import List, Optional, Tuple, TYPE_CHECKING

from ..outgoing_queue import enqueue_outgoing
from ..models.message import Message, MessageTopic
from ..models.peer import increment_peer_metric
from ...storage.models.atom import Atom
from ...storage.requests import get_atom_req_payload

if TYPE_CHECKING:
    from .. import Node
    from ..models.peer import Peer


class ObjectResponseType(IntEnum):
    OBJECT_FOUND = 0
    OBJECT_PROVIDER = 1
    OBJECT_NEAREST_PEER = 2
    OBJECT_PAYMENT_REQUIRED = 3


OBJECT_FOUND_ATOM_PAYLOAD = 1
OBJECT_FOUND_LIST_PAYLOAD = 2
OBJECT_PAYMENT_REQUIRED_NO_HINT_PAYLOAD_LEN = 32 + 8 + 8
OBJECT_PAYMENT_REQUIRED_WITH_HINT_PAYLOAD_LEN = OBJECT_PAYMENT_REQUIRED_NO_HINT_PAYLOAD_LEN + 32 + 4 + 2


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


def encode_object_payment_required(
    payment_public_key: bytes,
    storage_size_estimate: int,
    base_storage_fee: int,
    hint_peer: Optional[Tuple[bytes, str, int]] = None,
) -> bytes:
    """Encode payment-required payload with optional IPv4 relay hint.

    Format (no marker byte):
      - no hint: payment_public_key[32] + storage_size_estimate[8] + base_storage_fee[8]
      - with hint: base fields + hint_relay_public_key[32] + hint_ipv4[4] + hint_port[2]
    """
    payment_key = bytes(payment_public_key)
    if len(payment_key) != 32:
        raise ValueError("payment_public_key must be 32 bytes")
    try:
        storage_size_value = int(storage_size_estimate)
    except Exception as exc:
        raise ValueError("storage_size_estimate must be an integer") from exc
    try:
        base_storage_fee_value = int(base_storage_fee)
    except Exception as exc:
        raise ValueError("base_storage_fee must be an integer") from exc
    if not (0 <= storage_size_value <= ((1 << 64) - 1)):
        raise ValueError("storage_size_estimate must fit in u64")
    if not (0 <= base_storage_fee_value <= ((1 << 64) - 1)):
        raise ValueError("base_storage_fee must fit in u64")
    base_payload = (
        payment_key
        + storage_size_value.to_bytes(8, "big", signed=False)
        + base_storage_fee_value.to_bytes(8, "big", signed=False)
    )

    if hint_peer is None:
        return base_payload

    hint_public_key, hint_host, hint_port = hint_peer
    hint_key = bytes(hint_public_key)
    if len(hint_key) != 32:
        raise ValueError("hint relay public key must be 32 bytes")
    try:
        hint_ip_bytes = socket.inet_aton(hint_host)
    except OSError as exc:
        raise ValueError(f"invalid IPv4 address: {hint_host}") from exc
    if not (0 <= int(hint_port) <= 0xFFFF):
        raise ValueError(f"hint port out of range (0-65535): {hint_port}")

    hint_port_bytes = int(hint_port).to_bytes(2, "big", signed=False)
    return base_payload + hint_key + hint_ip_bytes + hint_port_bytes


def decode_object_payment_required(
    payload: bytes,
) -> Tuple[bytes, int, int, Optional[Tuple[bytes, str, int]]]:
    """Decode payment-required payload using length to determine optional hint."""
    payload_bytes = bytes(payload)
    if len(payload_bytes) == OBJECT_PAYMENT_REQUIRED_NO_HINT_PAYLOAD_LEN:
        payment_public_key = payload_bytes[:32]
        storage_size_estimate = int.from_bytes(payload_bytes[32:40], "big", signed=False)
        base_storage_fee = int.from_bytes(payload_bytes[40:48], "big", signed=False)
        return payment_public_key, storage_size_estimate, base_storage_fee, None

    if len(payload_bytes) != OBJECT_PAYMENT_REQUIRED_WITH_HINT_PAYLOAD_LEN:
        raise ValueError(
            "invalid OBJECT_PAYMENT_REQUIRED payload length "
            f"({len(payload_bytes)} bytes; expected 48 or 86)"
        )

    payment_public_key = payload_bytes[:32]
    storage_size_estimate = int.from_bytes(payload_bytes[32:40], "big", signed=False)
    base_storage_fee = int.from_bytes(payload_bytes[40:48], "big", signed=False)
    hint_public_key = payload_bytes[48:80]
    hint_ip_bytes = payload_bytes[80:84]
    hint_port_bytes = payload_bytes[84:86]
    hint_address = socket.inet_ntoa(hint_ip_bytes)
    hint_port = int.from_bytes(hint_port_bytes, "big", signed=False)
    return (
        payment_public_key,
        storage_size_estimate,
        base_storage_fee,
        (hint_public_key, hint_address, hint_port),
    )


def _retry_pending_object_get_via_peer_contact(
    node: "Node",
    *,
    atom_id: bytes,
    peer_contact: Tuple[bytes, str, int],
) -> bool:
    """Retry a pending OBJECT_GET via a provider/hint peer contact."""
    provider_key_bytes, provider_address, provider_port = peer_contact

    from .object_request import ObjectRequest, ObjectRequestType
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

    payload_type = get_atom_req_payload(node, atom_id)
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
        return False

    try:
        obj_req = ObjectRequest(
            type=ObjectRequestType.OBJECT_GET,
            data=b"",
            atom_id=atom_id,
            payload_type=payload_type,
        )
        obj_req_bytes = obj_req.to_bytes()
        obj_req_msg = Message(
            topic=MessageTopic.OBJECT_REQUEST,
            body=obj_req_bytes,
            sender=node.relay_public_key,
        )
        obj_req_msg.encrypt(shared_key_bytes)
        return bool(enqueue_outgoing(
            node,
            (provider_address, provider_port),
            message=obj_req_msg,
            difficulty=1,
        ))
    except Exception as exc:
        node.logger.warning(
            "Failed retrying OBJECT_GET for %s via %s:%s: %s",
            atom_id.hex(),
            provider_address,
            provider_port,
            exc,
        )
        return False


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
                increment_peer_metric(peer, "shared_storage_download", len(body))
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
                increment_peer_metric(
                    peer,
                    "shared_storage_download",
                    sum(len(atom.to_bytes()) for atom in atoms),
                )
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

            _retry_pending_object_get_via_peer_contact(
                node,
                atom_id=object_response.atom_id,
                peer_contact=(provider_key_bytes, provider_address, provider_port),
            )

        case ObjectResponseType.OBJECT_NEAREST_PEER:
            node.logger.debug("Ignoring OBJECT_NEAREST_PEER response from %s", peer.address)

        case ObjectResponseType.OBJECT_PAYMENT_REQUIRED:
            try:
                payment_public_key, storage_size_estimate, base_storage_fee, hint_peer = (
                    decode_object_payment_required(object_response.data)
                )
            except Exception as exc:
                node.logger.warning(
                    "Invalid OBJECT_PAYMENT_REQUIRED payload from %s: %s",
                    peer.address,
                    exc,
                )
                return
            node.logger.debug(
                "Received OBJECT_PAYMENT_REQUIRED from %s (payment_key=%s, size_estimate=%s, base_storage_fee=%s, hint=%s)",
                peer.address,
                payment_public_key.hex(),
                storage_size_estimate,
                base_storage_fee,
                hint_peer,
            )

            has_local_payment_key = bool(
                getattr(node, "relay_payment_secret_key", None)
                or (getattr(node, "config", {}) or {}).get("relay_payment_secret_key")
            )
            if has_local_payment_key:
                return

            if hint_peer is not None:
                node.logger.info(
                    "OBJECT_PAYMENT_REQUIRED for %s from %s but no local payment key; trying hint %s:%s",
                    object_response.atom_id.hex(),
                    peer.address,
                    hint_peer[1],
                    hint_peer[2],
                )
                if _retry_pending_object_get_via_peer_contact(
                    node,
                    atom_id=object_response.atom_id,
                    peer_contact=hint_peer,
                ):
                    return
                node.logger.info(
                    "Hint retry failed for %s after OBJECT_PAYMENT_REQUIRED from %s; ending request",
                    object_response.atom_id.hex(),
                    peer.address,
                )

            else:
                node.logger.info(
                    "OBJECT_PAYMENT_REQUIRED for %s from %s and no local payment key or hint; ending request",
                    object_response.atom_id.hex(),
                    peer.address,
                )

            node.pop_atom_req(object_response.atom_id)
            return
