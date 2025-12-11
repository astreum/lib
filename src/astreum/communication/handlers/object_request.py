import logging
import socket
from enum import IntEnum
from typing import TYPE_CHECKING, Tuple

from .object_response import ObjectResponse, ObjectResponseType
from ..models.message import Message, MessageTopic

if TYPE_CHECKING:
    from .. import Node
    from ..models.peer import Peer


class ObjectRequestType(IntEnum):
    OBJECT_GET = 0
    OBJECT_PUT = 1


class ObjectRequest:
    type: ObjectRequestType
    data: bytes
    atom_id: bytes

    def __init__(self, type: ObjectRequestType, data: bytes, atom_id: bytes = None):
        self.type = type
        self.data = data
        self.atom_id = atom_id

    def to_bytes(self):
        return [self.type.value] + self.atom_id + self.data

    @classmethod
    def from_bytes(cls, data: bytes) -> "ObjectRequest":
        # need at least 1 byte for type + 32 bytes for hash
        if len(data) < 1 + 32:
            raise ValueError(f"Too short for ObjectRequest ({len(data)} bytes)")

        type_val = data[0]
        try:
            req_type = ObjectRequestType(type_val)
        except ValueError:
            raise ValueError(f"Unknown ObjectRequestType: {type_val!r}")

        atom_id_bytes = data[1:33]
        payload    = data[33:]
        return cls(req_type, payload, atom_id_bytes)


def encode_peer_contact_bytes(peer: "Peer") -> bytes:
    """Return a fixed-width peer contact payload (32-byte key + IPv4 + port)."""
    if not peer.address:
        raise ValueError("peer address is required for encoding peer info")
    host, port = peer.address
    key_bytes = peer.public_key_bytes
    try:
        ip_bytes = socket.inet_aton(host)
    except OSError as exc:  # pragma: no cover - inet_aton raises for invalid hosts
        raise ValueError(f"invalid IPv4 address: {host}") from exc
    if not (0 <= port <= 0xFFFF):
        raise ValueError(f"port out of range (0-65535): {port}")
    port_bytes = int(port).to_bytes(2, "big", signed=False)
    return key_bytes + ip_bytes + port_bytes


def handle_object_request(node: "Node", addr: Tuple[str, int], message: Message) -> None:
    node_logger = getattr(node, "logger", logging.getLogger(__name__))
    try:
        object_request = ObjectRequest.from_bytes(message.body)
    except Exception as exc:
        node_logger.warning("Error decoding OBJECT_REQUEST from %s: %s", addr, exc)
        return

    match object_request.type:
        case ObjectRequestType.OBJECT_GET:
            atom_id = object_request.atom_id
            node_logger.debug("Handling OBJECT_GET for %s from %s", atom_id.hex(), addr)

            local_atom = node.local_get(atom_id)
            if local_atom is not None:
                node_logger.debug("Object %s found locally; returning to %s", atom_id.hex(), addr)
                resp = ObjectResponse(
                    type=ObjectResponseType.OBJECT_FOUND,
                    data=local_atom.to_bytes(),
                    atom_id=atom_id
                )
                obj_res_msg  = Message(
                    topic=MessageTopic.OBJECT_RESPONSE,
                    body=resp.to_bytes(),
                    sender=node.relay_public_key,
                )
                node.outgoing_queue.put((obj_res_msg.to_bytes(), addr))
                return

            storage_index = getattr(node, "storage_index", None) or {}
            if atom_id in storage_index:
                node_logger.debug("Known provider for %s; informing %s", atom_id.hex(), addr)
                provider_bytes = storage_index[atom_id]
                resp = ObjectResponse(
                    type=ObjectResponseType.OBJECT_PROVIDER,
                    data=provider_bytes,
                    atom_id=atom_id
                )
                obj_res_msg = Message(
                    topic=MessageTopic.OBJECT_RESPONSE,
                    body=resp.to_bytes(),
                    sender=node.relay_public_key,
                )
                node.outgoing_queue.put((obj_res_msg.to_bytes(), addr))
                return

            nearest_peer = node.peer_route.closest_peer_for_hash(atom_id)
            if nearest_peer:
                node_logger.debug("Forwarding requester %s to nearest peer for %s", addr, atom_id.hex())
                peer_info = encode_peer_contact_bytes(nearest_peer)
                resp = ObjectResponse(
                    type=ObjectResponseType.OBJECT_PROVIDER,
                    # type=ObjectResponseType.OBJECT_NEAREST_PEER,
                    data=peer_info,
                    atom_id=atom_id
                )
                obj_res_msg = Message(
                    topic=MessageTopic.OBJECT_RESPONSE,
                    body=resp.to_bytes(),
                    sender=node.relay_public_key,
                )
                node.outgoing_queue.put((obj_res_msg.to_bytes(), addr))

        case ObjectRequestType.OBJECT_PUT:
            atom_hash = object_request.data[:32]
            node_logger.debug("Handling OBJECT_PUT for %s from %s", atom_hash.hex(), addr)

            nearest_peer = node.peer_route.closest_peer_for_hash(atom_hash)
            nearest = (nearest_peer.public_key, nearest_peer) if nearest_peer else None
            if nearest:
                node_logger.debug("Forwarding OBJECT_PUT for %s to nearer peer %s", atom_hash.hex(), nearest[1].address)
                fwd_req = ObjectRequest(
                    type=ObjectRequestType.OBJECT_PUT,
                    data=object_request.data,
                )
                obj_req_msg = Message(
                    topic=MessageTopic.OBJECT_REQUEST,
                    body=fwd_req.to_bytes(),
                    sender=node.relay_public_key,
                )
                node.outgoing_queue.put((obj_req_msg.to_bytes(), nearest[1].address))
            else:
                node_logger.debug("Storing provider info for %s locally", atom_hash.hex())
                if not hasattr(node, "storage_index") or not isinstance(node.storage_index, dict):
                    node.storage_index = {}
                node.storage_index[atom_hash] = object_request.data[32:]

        case _:
            node_logger.warning("Unknown ObjectRequestType %s from %s", object_request.type, addr)
