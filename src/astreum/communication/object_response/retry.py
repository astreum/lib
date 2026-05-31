from typing import TYPE_CHECKING, Tuple

from ..models.message import Message, MessageTopic
from ..object_response.object_found import OBJECT_FOUND_ATOM_PAYLOAD
from ..outgoing_queue import enqueue_outgoing
from ...storage.requests import get_expr_req_payload

if TYPE_CHECKING:
    from .. import Node


def _retry_pending_object_get_via_peer_contact(
    node: "Node",
    *,
    atom_id: bytes,
    peer_contact: Tuple[bytes, str, int],
) -> bool:
    """Retry a pending OBJECT_GET via a provider/hint peer contact."""
    provider_key_bytes, provider_address, provider_port = peer_contact

    from ..object_request.code import ObjectRequestCode
    from ..object_request.model import ObjectRequest
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

    payload_type = get_expr_req_payload(node, atom_id)
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
            code=ObjectRequestCode.OBJECT_GET,
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
        return bool(
            enqueue_outgoing(
                node,
                (provider_address, provider_port),
                message=obj_req_msg,
                difficulty=1,
            )
        )
    except Exception as exc:
        node.logger.warning(
            "Failed retrying OBJECT_GET for %s via %s:%s: %s",
            atom_id.hex(),
            provider_address,
            provider_port,
            exc,
        )
        return False
