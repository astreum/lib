from typing import TYPE_CHECKING

from ..models.message import Message, MessageTopic
from ..models.peer import increment_peer_metric
from ..storage_request.code import StorageRequestCode
from ..storage_request.model import StorageRequest
from ..storage_request.payment_required import (
    _queue_storage_payment_required,
    _requires_storage_channel,
)
from ..storage_request.peer_contact import encode_peer_contact_bytes
from ..storage_response.code import StorageResponseCode
from ..storage_response.model import StorageResponse
from ..storage_response.storage_found import encode_payload
from ..outgoing_queue import enqueue_outgoing
from ...machine.models.expression import (
    RESOLUTION_SINGLE,
    RESOLUTION_LIST,
    RESOLUTION_FULL,
    collect_list,
    collect_full,
)
from ...storage.get.single.local import get_expr_from_local_storage
from ..util import xor_distance
from ...storage.providers import provider_id_for_payload, provider_payload_for_id

if TYPE_CHECKING:
    from .. import Node
    from ..models.peer import Peer


def _collect_for_resolution(expr, desired: int) -> list:
    """Collect exprs based on desired resolution, sending best available."""
    if desired >= RESOLUTION_FULL and expr._tag == "link":
        return collect_full(expr)
    if desired >= RESOLUTION_LIST and expr._tag == "link":
        return collect_list(expr)
    return [expr]


def handle_storage_request(node: "Node", peer: "Peer", message: Message) -> tuple[bool, str | None]:
    if message.content is None:
        node.logger.debug("STORAGE_REQUEST from %s missing content", peer.address)
        return False, "missing content"

    try:
        storage_request = StorageRequest.from_bytes(message.content)
    except Exception as exc:
        node.logger.debug("Error decoding STORAGE_REQUEST from %s: %s", peer.address, exc)
        return False, "decode failed"

    match storage_request.code:
        case StorageRequestCode.STORAGE_GET:
            expr_id = storage_request.expr_id
            node.logger.debug("Handling STORAGE_GET for %s from %s", expr_id.hex(), peer.address)
            desired = storage_request.payload_type or RESOLUTION_SINGLE

            local_atom = get_expr_from_local_storage(node, expr_id)
            if local_atom is not None:
                exprs = _collect_for_resolution(local_atom, desired)
                shared_storage_size = sum(len(e.to_bytes()) for e in exprs)
                if _requires_storage_channel(node, peer, shared_storage_size):
                    node.logger.info(
                        "Fair-use limit reached for %s while serving %s; channel/payment required",
                        peer.address,
                        expr_id.hex(),
                    )
                    _queue_storage_payment_required(
                        node,
                        peer,
                        expr_id,
                        shared_storage_size,
                    )
                    return True, None
                node.logger.debug(
                    "Expr %s found locally (resolution=%d, exprs=%d); returning to %s",
                    expr_id.hex(),
                    desired,
                    len(exprs),
                    peer.address,
                )
                resp = StorageResponse(
                    code=StorageResponseCode.STORAGE_FOUND,
                    data=encode_payload(exprs),
                    expr_id=expr_id,
                )
                resp_msg = Message(
                    topic=MessageTopic.STORAGE_RESPONSE,
                    body=resp.to_bytes(),
                    sender_public_key_bytes=node.storage_public_key_bytes,
                )
                resp_msg.encrypt(peer.shared_key_bytes)
                queued = enqueue_outgoing(
                    node,
                    peer.address,
                    message=resp_msg,
                    difficulty=peer.difficulty,
                )
                if queued:
                    increment_peer_metric(peer, "shared_storage_upload", shared_storage_size)
                return True, None

            if expr_id in node.storage_index:
                provider_id = node.storage_index[expr_id]
                provider_bytes = provider_payload_for_id(node, provider_id)
                if provider_bytes is not None:
                    node.logger.debug("Known provider for %s; informing %s", expr_id.hex(), peer.address)
                    resp = StorageResponse(
                        code=StorageResponseCode.STORAGE_PROVIDER,
                        data=provider_bytes,
                        expr_id=expr_id,
                    )
                    resp_msg = Message(
                        topic=MessageTopic.STORAGE_RESPONSE,
                        body=resp.to_bytes(),
                        sender_public_key_bytes=node.storage_public_key_bytes,
                    )
                    resp_msg.encrypt(peer.shared_key_bytes)
                    enqueue_outgoing(
                        node,
                        peer.address,
                        message=resp_msg,
                        difficulty=peer.difficulty,
                    )
                    return True, None
                node.logger.debug(
                    "Unknown provider id %s for %s",
                    provider_id,
                    expr_id.hex(),
                )

            nearest_peer = node.peer_route.closest_peer_for_hash(expr_id)
            if nearest_peer:
                node.logger.debug("Forwarding requester %s to nearest peer for %s", peer.address, expr_id.hex())
                peer_info = encode_peer_contact_bytes(nearest_peer)
                resp = StorageResponse(
                    code=StorageResponseCode.STORAGE_PROVIDER,
                    data=peer_info,
                    expr_id=expr_id,
                )
                resp_msg = Message(
                    topic=MessageTopic.STORAGE_RESPONSE,
                    body=resp.to_bytes(),
                    sender_public_key_bytes=node.storage_public_key_bytes,
                )
                resp_msg.encrypt(peer.shared_key_bytes)
                enqueue_outgoing(
                    node,
                    peer.address,
                    message=resp_msg,
                    difficulty=peer.difficulty,
                )
                return True, None

            if expr_id in node.storage_index:
                return False, f"unknown provider id {node.storage_index[expr_id]} for {expr_id.hex()}"
            return True, None

        case StorageRequestCode.STORAGE_PUT:
            node.logger.debug("Handling STORAGE_PUT for %s from %s", storage_request.expr_id.hex(), peer.address)

            nearest_peer = node.peer_route.closest_peer_for_hash(storage_request.expr_id)
            is_self_closest = False
            if nearest_peer is None or nearest_peer.address is None:
                is_self_closest = True
            else:
                try:
                    self_distance = xor_distance(storage_request.expr_id, node.storage_public_key_bytes)
                    peer_distance = xor_distance(storage_request.expr_id, nearest_peer.public_key_bytes)
                except Exception as exc:
                    node.logger.debug(
                        "Failed distance comparison for STORAGE_PUT %s: %s",
                        storage_request.expr_id.hex(),
                        exc,
                    )
                    is_self_closest = True
                else:
                    is_self_closest = self_distance <= peer_distance

            if is_self_closest:
                node.logger.debug("Storing provider info for %s locally", storage_request.expr_id.hex())
                provider_id = provider_id_for_payload(node, storage_request.data)
                node.storage_index[storage_request.expr_id] = provider_id
                print(
                    "STORAGE_PUT indexed provider expr_id=%s from=%s"
                    % (storage_request.expr_id.hex(), peer.address)
                )
                return True, None
            else:
                node.logger.debug(
                    "Forwarding STORAGE_PUT for %s to nearer peer %s",
                    storage_request.expr_id.hex(),
                    nearest_peer.address,
                )
                fwd_req = StorageRequest(
                    code=StorageRequestCode.STORAGE_PUT,
                    data=storage_request.data,
                    expr_id=storage_request.expr_id,
                    payload_type=storage_request.payload_type,
                )
                req_msg = Message(
                    topic=MessageTopic.STORAGE_REQUEST,
                    body=fwd_req.to_bytes(),
                    sender_public_key_bytes=node.storage_public_key_bytes,
                )
                req_msg.encrypt(nearest_peer.shared_key_bytes)
                enqueue_outgoing(
                    node,
                    nearest_peer.address,
                    message=req_msg,
                    difficulty=nearest_peer.difficulty,
                )
                return True, None

        case _:
            node.logger.debug("Unknown StorageRequestCode %s from %s", storage_request.code, peer.address)
            return False, f"unknown StorageRequestCode {storage_request.code}"

    return True, None
