import logging
import socket
from enum import IntEnum
from typing import Optional, TYPE_CHECKING, Tuple

from .object_response import (
    ObjectResponse,
    ObjectResponseType,
    OBJECT_FOUND_ATOM_PAYLOAD,
    OBJECT_FOUND_LIST_PAYLOAD,
    encode_object_found_atom_payload,
    encode_object_found_list_payload,
    encode_object_payment_required,
)
from ..outgoing_queue import enqueue_outgoing
from ..models.message import Message, MessageTopic
from ..models.peer import increment_peer_metric
from ..util import xor_distance
from ...storage.providers import provider_id_for_payload, provider_payload_for_id

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
    payload_type: Optional[int]

    def __init__(
        self,
        type: ObjectRequestType,
        data: bytes = b"",
        atom_id: bytes = None,
        payload_type: Optional[int] = None,
    ):
        self.type = type
        self.data = data
        self.atom_id = atom_id
        self.payload_type = payload_type

    def to_bytes(self):
        if self.type == ObjectRequestType.OBJECT_PUT and self.payload_type is None:
            raise ValueError("OBJECT_PUT requires payload_type")
        if self.payload_type is not None:
            payload = bytes([self.payload_type]) + self.data
        else:
            payload = self.data
        return bytes([self.type.value]) + self.atom_id + payload

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
        payload = data[33:]
        if req_type == ObjectRequestType.OBJECT_GET:
            if payload:
                payload_type = payload[0]
                payload = payload[1:]
            else:
                payload_type = None
            return cls(req_type, payload, atom_id_bytes, payload_type=payload_type)
        if req_type == ObjectRequestType.OBJECT_PUT:
            if not payload:
                raise ValueError("OBJECT_PUT missing payload type")
            payload_type = payload[0]
            payload = payload[1:]
            return cls(req_type, payload, atom_id_bytes, payload_type=payload_type)
        return cls(req_type, payload, atom_id_bytes)


def encode_peer_contact_bytes(peer: "Peer") -> bytes:
    """Return a fixed-width peer contact payload (32-byte key + IPv4 + port)."""
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


def _requires_storage_channel(node: "Node", peer: "Peer", next_upload_bytes: int) -> bool:
    """Return True when a peer must use a payment/channel before another object share."""
    pending_upload = int(next_upload_bytes)
    if pending_upload <= 0:
        return False

    fair_use_limit = node.config["fair_use_limit"]
    fair_use_ratio = node.config["fair_use_ratio"]
    if fair_use_ratio <= 0:
        return False

    with peer.metrics_lock:
        current_upload = peer.shared_storage_upload
        current_download = peer.shared_storage_download

    projected_upload = current_upload + pending_upload
    if projected_upload < fair_use_limit:
        return False
    if projected_upload <= 0:
        return False

    return (current_download / projected_upload) < fair_use_ratio


def _queue_object_payment_required(
    node: "Node",
    peer: "Peer",
    atom_id: bytes,
    storage_size_estimate: int,
) -> bool:
    """Queue an OBJECT_PAYMENT_REQUIRED response for a peer."""
    payment_public_key = (getattr(node, "config", {}) or {}).get("relay_payment_public_key_bytes")
    if not isinstance(payment_public_key, (bytes, bytearray)) or len(payment_public_key) != 32:
        node.logger.warning(
            "Cannot send OBJECT_PAYMENT_REQUIRED for %s to %s: relay payment public key is unavailable",
            atom_id.hex(),
            peer.address,
        )
        return False

    try:
        base_storage_fee = int(getattr(node, "storage_request_current_price", 0) or 0)
    except Exception:
        base_storage_fee = 0
    if base_storage_fee < 0:
        base_storage_fee = 0

    try:
        payload = encode_object_payment_required(
            payment_public_key=bytes(payment_public_key),
            storage_size_estimate=int(storage_size_estimate),
            base_storage_fee=base_storage_fee,
            hint_peer=None,
        )
    except Exception as exc:
        node.logger.warning(
            "Failed encoding OBJECT_PAYMENT_REQUIRED for %s to %s: %s",
            atom_id.hex(),
            peer.address,
            exc,
        )
        return False

    try:
        response = ObjectResponse(
            type=ObjectResponseType.OBJECT_PAYMENT_REQUIRED,
            data=payload,
            atom_id=atom_id,
        )
        msg = Message(
            topic=MessageTopic.OBJECT_RESPONSE,
            body=response.to_bytes(),
            sender=node.relay_public_key,
        )
        msg.encrypt(peer.shared_key_bytes)
        queued = enqueue_outgoing(
            node,
            peer.address,
            message=msg,
            difficulty=peer.difficulty,
        )
    except Exception as exc:
        node.logger.warning(
            "Failed queueing OBJECT_PAYMENT_REQUIRED for %s to %s: %s",
            atom_id.hex(),
            peer.address,
            exc,
        )
        return False

    if queued:
        node.logger.info(
            "Queued OBJECT_PAYMENT_REQUIRED for %s to %s (size_estimate=%s base_storage_fee=%s)",
            atom_id.hex(),
            peer.address,
            int(storage_size_estimate),
            base_storage_fee,
        )
        return True

    node.logger.debug(
        "Dropped OBJECT_PAYMENT_REQUIRED for %s to %s",
        atom_id.hex(),
        peer.address,
    )
    return False


def handle_object_request(node: "Node", peer: "Peer", message: Message) -> None:
    if message.content is None:
        node.logger.warning("OBJECT_REQUEST from %s missing content", peer.address)
        return

    try:
        object_request = ObjectRequest.from_bytes(message.content)
    except Exception as exc:
        node.logger.warning("Error decoding OBJECT_REQUEST from %s: %s", peer.address, exc)
        return

    match object_request.type:
        case ObjectRequestType.OBJECT_GET:
            atom_id = object_request.atom_id
            node.logger.debug("Handling OBJECT_GET for %s from %s", atom_id.hex(), peer.address)
            payload_type = object_request.payload_type
            if payload_type is None:
                payload_type = OBJECT_FOUND_ATOM_PAYLOAD

            if payload_type == OBJECT_FOUND_ATOM_PAYLOAD:
                local_atom = node.get_atom_from_local_storage(atom_id=atom_id)
                if local_atom is not None:
                    shared_storage_size = len(local_atom.to_bytes())
                    if _requires_storage_channel(node, peer, shared_storage_size):
                        node.logger.info(
                            "Fair-use limit reached for %s while serving atom %s; channel/payment required",
                            peer.address,
                            atom_id.hex(),
                        )
                        _queue_object_payment_required(
                            node,
                            peer,
                            atom_id,
                            shared_storage_size,
                        )
                        return
                    node.logger.debug("Object %s found locally; returning to %s", atom_id.hex(), peer.address)
                    resp = ObjectResponse(
                        type=ObjectResponseType.OBJECT_FOUND,
                        data=encode_object_found_atom_payload(local_atom),
                        atom_id=atom_id
                    )
                    obj_res_msg  = Message(
                        topic=MessageTopic.OBJECT_RESPONSE,
                        body=resp.to_bytes(),
                        sender=node.relay_public_key,
                    )
                    obj_res_msg.encrypt(peer.shared_key_bytes)
                    queued = enqueue_outgoing(
                        node,
                        peer.address,
                        message=obj_res_msg,
                        difficulty=peer.difficulty,
                    )
                    if queued:
                        increment_peer_metric(peer, "shared_storage_upload", shared_storage_size)
                    return
            elif payload_type == OBJECT_FOUND_LIST_PAYLOAD:
                node.logger.debug(
                    "OBJECT_GET list request atom_id=%s from=%s",
                    atom_id.hex(),
                    peer.address,
                )
                local_atoms = node.get_atom_list_from_local_storage(root_hash=atom_id)
                if local_atoms is not None:
                    shared_storage_size = sum(len(atom.to_bytes()) for atom in local_atoms)
                    if _requires_storage_channel(node, peer, shared_storage_size):
                        node.logger.info(
                            "Fair-use limit reached for %s while serving list %s; channel/payment required",
                            peer.address,
                            atom_id.hex(),
                        )
                        _queue_object_payment_required(
                            node,
                            peer,
                            atom_id,
                            shared_storage_size,
                        )
                        return
                    node.logger.debug("Object list %s found locally; returning to %s", atom_id.hex(), peer.address)
                    resp = ObjectResponse(
                        type=ObjectResponseType.OBJECT_FOUND,
                        data=encode_object_found_list_payload(local_atoms),
                        atom_id=atom_id
                    )
                    obj_res_msg  = Message(
                        topic=MessageTopic.OBJECT_RESPONSE,
                        body=resp.to_bytes(),
                        sender=node.relay_public_key,
                    )
                    obj_res_msg.encrypt(peer.shared_key_bytes)
                    queued = enqueue_outgoing(
                        node,
                        peer.address,
                        message=obj_res_msg,
                        difficulty=peer.difficulty,
                    )
                    if queued:
                        increment_peer_metric(peer, "shared_storage_upload", shared_storage_size)
                    return
            else:
                node.logger.warning(
                    "Unknown OBJECT_GET payload type %s for %s",
                    payload_type,
                    atom_id.hex(),
                )

            if atom_id in node.storage_index:
                provider_id = node.storage_index[atom_id]
                provider_bytes = provider_payload_for_id(node, provider_id)
                if provider_bytes is not None:
                    node.logger.debug("Known provider for %s; informing %s", atom_id.hex(), peer.address)
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
                    obj_res_msg.encrypt(peer.shared_key_bytes)
                    enqueue_outgoing(
                        node,
                        peer.address,
                        message=obj_res_msg,
                        difficulty=peer.difficulty,
                    )
                    return
                node.logger.warning(
                    "Unknown provider id %s for %s",
                    provider_id,
                    atom_id.hex(),
                )

            nearest_peer = node.peer_route.closest_peer_for_hash(atom_id)
            if nearest_peer:
                node.logger.debug("Forwarding requester %s to nearest peer for %s", peer.address, atom_id.hex())
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
                obj_res_msg.encrypt(peer.shared_key_bytes)
                enqueue_outgoing(
                    node,
                    peer.address,
                    message=obj_res_msg,
                    difficulty=peer.difficulty,
                )

        case ObjectRequestType.OBJECT_PUT:
            node.logger.debug("Handling OBJECT_PUT for %s from %s", object_request.atom_id.hex(), peer.address)

            nearest_peer = node.peer_route.closest_peer_for_hash(object_request.atom_id)
            is_self_closest = False
            if nearest_peer is None or nearest_peer.address is None:
                is_self_closest = True
            else:
                try:
                    self_distance = xor_distance(object_request.atom_id, node.relay_public_key_bytes)
                    peer_distance = xor_distance(object_request.atom_id, nearest_peer.public_key_bytes)
                except Exception as exc:
                    node.logger.warning(
                        "Failed distance comparison for OBJECT_PUT %s: %s",
                        object_request.atom_id.hex(),
                        exc,
                    )
                    is_self_closest = True
                else:
                    is_self_closest = self_distance <= peer_distance

            if is_self_closest:
                node.logger.debug("Storing provider info for %s locally", object_request.atom_id.hex())
                provider_id = provider_id_for_payload(node, object_request.data)
                node.storage_index[object_request.atom_id] = provider_id
                print(
                    "OBJECT_PUT indexed provider atom_id=%s from=%s"
                    % (object_request.atom_id.hex(), peer.address)
                )
            else:
                node.logger.debug(
                    "Forwarding OBJECT_PUT for %s to nearer peer %s",
                    object_request.atom_id.hex(),
                    nearest_peer.address,
                )
                fwd_req = ObjectRequest(
                    type=ObjectRequestType.OBJECT_PUT,
                    data=object_request.data,
                    atom_id=object_request.atom_id,
                    payload_type=object_request.payload_type,
                )
                obj_req_msg = Message(
                    topic=MessageTopic.OBJECT_REQUEST,
                    body=fwd_req.to_bytes(),
                    sender=node.relay_public_key,
                )
                obj_req_msg.encrypt(nearest_peer.shared_key_bytes)
                enqueue_outgoing(
                    node,
                    nearest_peer.address,
                    message=obj_req_msg,
                    difficulty=nearest_peer.difficulty,
                )

        case _:
            node.logger.warning("Unknown ObjectRequestType %s from %s", object_request.type, peer.address)
