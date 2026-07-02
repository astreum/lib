from typing import TYPE_CHECKING, Tuple

from ..models.message import Message, MessageTopic
from ...machine.models.expression import RESOLUTION_SINGLE
from ..outgoing_queue import enqueue_outgoing
from ...storage.requests import get_expr_req_payload

if TYPE_CHECKING:
    from .. import Node


def _retry_pending_storage_get_via_peer_contact(
    node: "Node",
    *,
    expr_id: bytes,
    peer_contact: Tuple[bytes, str, int],
) -> bool:
    """Retry a pending STORAGE_GET via a provider/hint peer contact."""
    provider_key_bytes, provider_address, provider_port = peer_contact

    from ..storage_request.code import StorageRequestCode
    from ..storage_request.model import StorageRequest
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

    payload_type = get_expr_req_payload(node, expr_id)
    if payload_type is None:
        payload_type = RESOLUTION_SINGLE

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
        req = StorageRequest(
            code=StorageRequestCode.STORAGE_GET,
            data=b"",
            expr_id=expr_id,
            payload_type=payload_type,
        )
        req_bytes = req.to_bytes()
        req_msg = Message(
            topic=MessageTopic.STORAGE_REQUEST,
            body=req_bytes,
            sender_public_key_bytes=node.storage_public_key_bytes,
        )
        req_msg.encrypt(shared_key_bytes)
        return bool(
            enqueue_outgoing(
                node,
                (provider_address, provider_port),
                message=req_msg,
                difficulty=1,
            )
        )
    except Exception as exc:
        node.logger.warning(
            "Failed retrying STORAGE_GET for %s via %s:%s: %s",
            expr_id.hex(),
            provider_address,
            provider_port,
            exc,
        )
        return False
