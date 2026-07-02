from typing import TYPE_CHECKING

from ..models.message import Message, MessageTopic
from ..models.peer import increment_peer_metric
from ..object_request.code import ObjectRequestCode
from ..object_request.model import ObjectRequest
from ..object_request.payment_required import (
    _queue_object_payment_required,
    _requires_storage_channel,
)
from ..object_request.peer_contact import encode_peer_contact_bytes
from ..object_response.code import ObjectResponseCode
from ..object_response.model import ObjectResponse
from ..object_response.object_found import encode_payload
from ..outgoing_queue import enqueue_outgoing
from ...machine.models.expression import (
    RESOLUTION_SINGLE,
    RESOLUTION_LIST,
    RESOLUTION_FULL,
    collect_list,
    collect_full,
)
from ...storage.actions.get import get_expr_from_local_storage
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


def handle_object_request(node: "Node", peer: "Peer", message: Message) -> tuple[bool, str | None]:
    if message.content is None:
        node.logger.debug("OBJECT_REQUEST from %s missing content", peer.address)
        return False, "missing content"

    try:
        object_request = ObjectRequest.from_bytes(message.content)
    except Exception as exc:
        node.logger.debug("Error decoding OBJECT_REQUEST from %s: %s", peer.address, exc)
        return False, "decode failed"

    match object_request.code:
        case ObjectRequestCode.OBJECT_GET:
            atom_id = object_request.atom_id
            node.logger.debug("Handling OBJECT_GET for %s from %s", atom_id.hex(), peer.address)
            desired = object_request.payload_type or RESOLUTION_SINGLE

            local_atom = get_expr_from_local_storage(node, atom_id)
            if local_atom is not None:
                exprs = _collect_for_resolution(local_atom, desired)
                shared_storage_size = sum(len(e.to_bytes()) for e in exprs)
                if _requires_storage_channel(node, peer, shared_storage_size):
                    node.logger.info(
                        "Fair-use limit reached for %s while serving %s; channel/payment required",
                        peer.address,
                        atom_id.hex(),
                    )
                    _queue_object_payment_required(
                        node,
                        peer,
                        atom_id,
                        shared_storage_size,
                    )
                    return True, None
                node.logger.debug(
                    "Object %s found locally (resolution=%d, exprs=%d); returning to %s",
                    atom_id.hex(),
                    desired,
                    len(exprs),
                    peer.address,
                )
                resp = ObjectResponse(
                    code=ObjectResponseCode.OBJECT_FOUND,
                    data=encode_payload(exprs),
                    atom_id=atom_id,
                )
                obj_res_msg = Message(
                    topic=MessageTopic.OBJECT_RESPONSE,
                    body=resp.to_bytes(),
                    sender_public_key_bytes=node.storage_public_key_bytes,
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
                return True, None

            if atom_id in node.storage_index:
                provider_id = node.storage_index[atom_id]
                provider_bytes = provider_payload_for_id(node, provider_id)
                if provider_bytes is not None:
                    node.logger.debug("Known provider for %s; informing %s", atom_id.hex(), peer.address)
                    resp = ObjectResponse(
                        code=ObjectResponseCode.OBJECT_PROVIDER,
                        data=provider_bytes,
                        atom_id=atom_id,
                    )
                    obj_res_msg = Message(
                        topic=MessageTopic.OBJECT_RESPONSE,
                        body=resp.to_bytes(),
                        sender_public_key_bytes=node.storage_public_key_bytes,
                    )
                    obj_res_msg.encrypt(peer.shared_key_bytes)
                    enqueue_outgoing(
                        node,
                        peer.address,
                        message=obj_res_msg,
                        difficulty=peer.difficulty,
                    )
                    return True, None
                node.logger.debug(
                    "Unknown provider id %s for %s",
                    provider_id,
                    atom_id.hex(),
                )

            nearest_peer = node.peer_route.closest_peer_for_hash(atom_id)
            if nearest_peer:
                node.logger.debug("Forwarding requester %s to nearest peer for %s", peer.address, atom_id.hex())
                peer_info = encode_peer_contact_bytes(nearest_peer)
                resp = ObjectResponse(
                    code=ObjectResponseCode.OBJECT_PROVIDER,
                    data=peer_info,
                    atom_id=atom_id,
                )
                obj_res_msg = Message(
                    topic=MessageTopic.OBJECT_RESPONSE,
                    body=resp.to_bytes(),
                    sender_public_key_bytes=node.storage_public_key_bytes,
                )
                obj_res_msg.encrypt(peer.shared_key_bytes)
                enqueue_outgoing(
                    node,
                    peer.address,
                    message=obj_res_msg,
                    difficulty=peer.difficulty,
                )
                return True, None

            if atom_id in node.storage_index:
                return False, f"unknown provider id {node.storage_index[atom_id]} for {atom_id.hex()}"
            return True, None

        case ObjectRequestCode.OBJECT_PUT:
            node.logger.debug("Handling OBJECT_PUT for %s from %s", object_request.atom_id.hex(), peer.address)

            nearest_peer = node.peer_route.closest_peer_for_hash(object_request.atom_id)
            is_self_closest = False
            if nearest_peer is None or nearest_peer.address is None:
                is_self_closest = True
            else:
                try:
                    self_distance = xor_distance(object_request.atom_id, node.storage_public_key_bytes)
                    peer_distance = xor_distance(object_request.atom_id, nearest_peer.public_key_bytes)
                except Exception as exc:
                    node.logger.debug(
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
                return True, None
            else:
                node.logger.debug(
                    "Forwarding OBJECT_PUT for %s to nearer peer %s",
                    object_request.atom_id.hex(),
                    nearest_peer.address,
                )
                fwd_req = ObjectRequest(
                    code=ObjectRequestCode.OBJECT_PUT,
                    data=object_request.data,
                    atom_id=object_request.atom_id,
                    payload_type=object_request.payload_type,
                )
                obj_req_msg = Message(
                    topic=MessageTopic.OBJECT_REQUEST,
                    body=fwd_req.to_bytes(),
                    sender_public_key_bytes=node.storage_public_key_bytes,
                )
                obj_req_msg.encrypt(nearest_peer.shared_key_bytes)
                enqueue_outgoing(
                    node,
                    nearest_peer.address,
                    message=obj_req_msg,
                    difficulty=nearest_peer.difficulty,
                )
                return True, None

        case _:
            node.logger.debug("Unknown ObjectRequestCode %s from %s", object_request.code, peer.address)
            return False, f"unknown ObjectRequestCode {object_request.code}"

    return True, None
