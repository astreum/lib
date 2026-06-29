from typing import TYPE_CHECKING

from ..models.message import Message
from ..models.peer import increment_peer_metric
from ..object_response.object_found import (
    OBJECT_FOUND_ATOM_PAYLOAD,
    OBJECT_FOUND_LIST_PAYLOAD,
    decode_object_found_expr_list_payload,
)
from ..object_response.code import ObjectResponseCode
from ..object_response.model import ObjectResponse
from ..object_response.object_payment_required import decode_object_payment_required
from ..object_response.object_provider import decode_object_provider
from ..object_response.retry import _retry_pending_object_get_via_peer_contact
from ...machine.models.expression import Expr

if TYPE_CHECKING:
    from .. import Node
    from ..models.peer import Peer

def handle_object_response(node: "Node", peer: "Peer", message: Message) -> tuple[bool, str | None]:
    if message.content is None:
        node.logger.debug("OBJECT_RESPONSE from %s missing content", peer.address)
        return False, "missing content"

    try:
        object_response = ObjectResponse.from_bytes(message.content)
    except Exception as exc:
        node.logger.debug("Error decoding OBJECT_RESPONSE from %s: %s", peer.address, exc)
        return False, "decode failed"

    if not node.has_expr_req(object_response.atom_id):
        return True, None

    match object_response.code:
        case ObjectResponseCode.OBJECT_FOUND:
            payload = object_response.data
            if not payload:
                node.logger.debug(
                    "OBJECT_FOUND payload for %s missing content",
                    object_response.atom_id.hex(),
                )
                return False, "OBJECT_FOUND payload missing content"

            payload_type = payload[0]
            body = payload[1:]

            if payload_type == OBJECT_FOUND_ATOM_PAYLOAD:
                try:
                    expr = Expr.from_bytes(body)
                except Exception as exc:
                    node.logger.debug(
                        "Invalid OBJECT_FOUND expr payload for %s: %s",
                        object_response.atom_id.hex(),
                        exc,
                    )
                    return False, "invalid OBJECT_FOUND expr payload"

                expr_id = expr.hash()
                if object_response.atom_id != expr_id:
                    node.logger.debug(
                        "OBJECT_FOUND expr ID mismatch (expected=%s got=%s)",
                        object_response.atom_id.hex(),
                        expr_id.hex(),
                    )
                    return False, "OBJECT_FOUND expr ID mismatch"

                node.pop_expr_req(expr_id)
                increment_peer_metric(peer, "shared_storage_download", len(body))
                if not node._hot_storage_set(expr):
                    return False, f"failed hot storage set for expr {expr_id.hex()}"
                return True, None

            if payload_type == OBJECT_FOUND_LIST_PAYLOAD:
                try:
                    exprs = decode_object_found_expr_list_payload(body)
                except Exception as exc:
                    node.logger.debug(
                        "Invalid OBJECT_FOUND list payload for %s: %s",
                        object_response.atom_id.hex(),
                        exc,
                    )
                    return False, "invalid OBJECT_FOUND list payload"

                if not exprs:
                    node.logger.debug(
                        "OBJECT_FOUND list payload for %s contained no exprs",
                        object_response.atom_id.hex(),
                    )
                    return False, "OBJECT_FOUND list payload contained no exprs"

                node.logger.debug(
                    "OBJECT_FOUND list response atom_id=%s exprs=%s",
                    object_response.atom_id.hex(),
                    len(exprs),
                )
                root_id = exprs[0].hash()
                if object_response.atom_id != root_id:
                    node.logger.debug(
                        "OBJECT_FOUND list root ID mismatch (expected=%s got=%s)",
                        object_response.atom_id.hex(),
                        root_id.hex(),
                    )
                    return False, "OBJECT_FOUND list root ID mismatch"

                node.pop_expr_req(root_id)
                increment_peer_metric(
                    peer,
                    "shared_storage_download",
                    sum(len(expr.to_bytes()) for expr in exprs),
                )
                hot_store_failures = 0
                for expr in exprs:
                    if not node._hot_storage_set(expr):
                        hot_store_failures += 1
                if hot_store_failures:
                    return (
                        False,
                        f"failed hot storage set for list {root_id.hex()} count={hot_store_failures}",
                    )
                return True, None

            node.logger.debug(
                "Unknown OBJECT_FOUND payload type %s for %s",
                payload_type,
                object_response.atom_id.hex(),
            )
            return False, f"unknown OBJECT_FOUND payload type {payload_type}"

        case ObjectResponseCode.OBJECT_PROVIDER:
            try:
                storage_key_bytes, relay_key_bytes, provider_address, provider_port = decode_object_provider(
                    object_response.data
                )
            except Exception as exc:
                node.logger.debug("Invalid OBJECT_PROVIDER payload from %s: %s", peer.address, exc)
                return False, "invalid OBJECT_PROVIDER payload"

            _retry_pending_object_get_via_peer_contact(
                node,
                atom_id=object_response.atom_id,
                peer_contact=(relay_key_bytes, provider_address, provider_port),
            )
            return True, None

        case ObjectResponseCode.OBJECT_PAYMENT_REQUIRED:
            try:
                payment_public_key, storage_size_estimate, base_storage_fee, hint_peer = (
                    decode_object_payment_required(object_response.data)
                )
            except Exception as exc:
                node.logger.debug(
                    "Invalid OBJECT_PAYMENT_REQUIRED payload from %s: %s",
                    peer.address,
                    exc,
                )
                return False, "invalid OBJECT_PAYMENT_REQUIRED payload"
            node.logger.debug(
                "Received OBJECT_PAYMENT_REQUIRED from %s (payment_key=%s, size_estimate=%s, base_storage_fee=%s, hint=%s)",
                peer.address,
                payment_public_key.hex(),
                storage_size_estimate,
                base_storage_fee,
                hint_peer,
            )

            has_local_payment_key = bool(
                getattr(node, "storage_secret_key", None)
                or (getattr(node, "config", {}) or {}).get("storage_secret_key")
            )
            if has_local_payment_key:
                return True, None

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
                    return True, None
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

            node.pop_expr_req(object_response.atom_id)
            return True, None

        case _:
            return False, f"unknown ObjectResponseCode {object_response.code}"
