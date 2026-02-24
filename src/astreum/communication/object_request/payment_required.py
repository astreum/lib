from typing import TYPE_CHECKING

from ..models.message import Message, MessageTopic
from ..object_response.code import ObjectResponseCode
from ..object_response.model import ObjectResponse
from ..object_response.object_payment_required import encode_object_payment_required
from ..outgoing_queue import enqueue_outgoing

if TYPE_CHECKING:
    from .. import Node
    from ..models.peer import Peer


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
            code=ObjectResponseCode.OBJECT_PAYMENT_REQUIRED,
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

