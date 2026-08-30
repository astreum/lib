from __future__ import annotations

import socket

from time import sleep
from typing import Optional

from astreum.storage.exprs.local import get_expr_from_local_storage
from astreum.storage.requests import add_expr_req
from astreum.expression import Expr, RESOLUTION_SINGLE, RESOLUTION_LIST, RESOLUTION_FULL


def _collect_missing_hashes(expr: Expr, resolution: int) -> list[bytes]:
    """Return unresolved hashes from a partially-resolved expr."""
    missing: list[bytes] = []
    if resolution == RESOLUTION_LIST:
        current = expr
        while current is not None and current._tag == "link":
            if current._tail_hash is not None:
                missing.append(current._tail_hash)
                break
            current = current._tail
    elif resolution == RESOLUTION_FULL:
        stack = [expr]
        while stack:
            e = stack.pop()
            if e._tag != "link":
                continue
            if e._head is not None:
                stack.append(e._head)
            elif e._head_hash is not None:
                missing.append(e._head_hash)
            if e._tail is not None:
                stack.append(e._tail)
            elif e._tail_hash is not None:
                missing.append(e._tail_hash)
    return missing


def _send_storage_request(node, expr_id: bytes, resolution: int) -> Optional[str]:
    """Send a STORAGE_GET request to a peer. Returns error string or None."""
    from astreum.communication.storage_request.code import StorageRequestCode
    from astreum.communication.storage_request.model import StorageRequest
    from astreum.communication.models.message import Message, MessageTopic
    from astreum.communication.outgoing_queue import enqueue_outgoing

    provider_id = node.storage_index.get(expr_id)
    if provider_id is not None:
        from astreum.storage.providers import provider_payload_for_id
        from astreum.communication.storage_response.storage_provider import decode_storage_provider
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

        provider_payload = provider_payload_for_id(node, provider_id)
        if provider_payload is not None:
            try:
                storage_key_bytes, relay_key_bytes, provider_address, provider_port = decode_storage_provider(provider_payload)
                provider_public_key = X25519PublicKey.from_public_bytes(relay_key_bytes)
                shared_key_bytes = node.relay_secret_key.exchange(provider_public_key)

                storage_req = StorageRequest(
                    code=StorageRequestCode.STORAGE_GET,
                    data=b"",
                    expr_id=expr_id,
                    payload_type=resolution,
                )
                message = Message(
                    topic=MessageTopic.STORAGE_REQUEST,
                    content=storage_req.to_bytes(),
                    sender_public_key_bytes=node.storage_public_key_bytes,
                )
                message.encrypt(shared_key_bytes)
                add_expr_req(node, expr_id, resolution)
                queued = enqueue_outgoing(
                    node,
                    (provider_address, provider_port),
                    message=message,
                    difficulty=1,
                )
                if queued:
                    node.logger.debug(
                        "Requested %s %s from indexed provider %s:%s",
                        resolution,
                        expr_id.hex(),
                        provider_address,
                        provider_port,
                    )
                else:
                    node.logger.debug(
                        "Dropped request for %s %s to indexed provider %s:%s",
                        resolution,
                        expr_id.hex(),
                        provider_address,
                        provider_port,
                    )
                return None
            except Exception as exc:
                node.logger.debug("Failed indexed fetch for %s: %s", expr_id.hex(), exc)
                return f"failed indexed fetch: {exc}"
        return f"unknown provider id {provider_id}"

    try:
        closest_peer = node.peer_route.closest_peer_for_hash(expr_id)
    except Exception as exc:
        return f"peer lookup failed: {exc}"

    if closest_peer is None or closest_peer.address is None:
        return "no peer available"

    storage_req = StorageRequest(
        code=StorageRequestCode.STORAGE_GET,
        data=b"",
        expr_id=expr_id,
        payload_type=resolution,
    )
    try:
        message = Message(
            topic=MessageTopic.STORAGE_REQUEST,
            content=storage_req.to_bytes(),
            sender_public_key_bytes=node.storage_public_key_bytes,
        )
    except Exception as exc:
        return f"failed to build storage request: {exc}"

    message.encrypt(closest_peer.shared_key_bytes)
    add_expr_req(node, expr_id, resolution)

    try:
        queued = enqueue_outgoing(
            node,
            closest_peer.address,
            message=message,
            difficulty=closest_peer.difficulty,
        )
        if queued:
            node.logger.debug(
                "Queued STORAGE_GET %s for %s to peer %s",
                resolution,
                expr_id.hex(),
                closest_peer.address,
            )
        else:
            node.logger.debug(
                "Dropped STORAGE_GET %s for %s to peer %s",
                resolution,
                expr_id.hex(),
                closest_peer.address,
            )
    except Exception as exc:
        return f"failed to queue STORAGE_GET: {exc}"
    return None


def get_expr_from_network(node, expr_id: bytes, resolution: int = RESOLUTION_SINGLE) -> Optional[Expr]:
    """Fetch an Expr from the P2P network with polling.

    Sends a ``STORAGE_GET`` request to an indexed provider or closest
    peer, then polls local storage with retries until the response
    arrives.  For ``RESOLUTION_LIST`` / ``RESOLUTION_FULL``, the
    response is inspected via ``_collect_missing_hashes`` and any
    unresolved inner hashes are fetched recursively as
    ``RESOLUTION_SINGLE`` requests.

    Args:
        node: A Node instance providing config and storage access.
        expr_id: The content hash of the expression to fetch.
        resolution: The resolution strategy — ``RESOLUTION_SINGLE``
            (default), ``RESOLUTION_LIST``, or ``RESOLUTION_FULL``.

    Returns:
        The fetched Expr, or None if all retries are exhausted or the
        node is disconnected.
    """
    if not node.is_connected:
        node.logger.debug("Network fetch skipped for %s; node not connected", expr_id.hex())
        return None

    node.logger.debug("Attempting network fetch for %s (resolution=%s)", expr_id.hex(), resolution)

    err = _send_storage_request(node, expr_id, resolution)
    if err is not None:
        node.logger.debug("Network request failed for %s: %s", expr_id.hex(), err)
        return None

    interval = node.config["storage_fetch_interval"]
    retries = node.config["storage_fetch_retries"]

    def _poll_single() -> Optional[Expr]:
        if interval <= 0 or retries <= 0:
            return get_expr_from_local_storage(node, expr_id)
        for _ in range(retries):
            expr = get_expr_from_local_storage(node, expr_id)
            if expr is not None:
                return expr
            sleep(interval)
        return get_expr_from_local_storage(node, expr_id)

    def _poll_list() -> Optional[Expr]:
        from astreum.storage.exprs.list import get_expr_list_from_local_storage

        for attempt in range(max(retries, 1)):
            raw = get_expr_list_from_local_storage(node, expr_id)
            if raw is not None:
                missing = _collect_missing_hashes(raw, RESOLUTION_LIST)
                if not missing:
                    return raw
                for h in missing:
                    get_expr_from_network(node, h, RESOLUTION_SINGLE)
            else:
                sleep(interval)
        return get_expr_list_from_local_storage(node, expr_id)

    def _poll_full() -> Optional[Expr]:
        from astreum.storage.exprs.full import get_expr_full_from_local_storage

        for attempt in range(max(retries, 1)):
            raw = get_expr_full_from_local_storage(node, expr_id)
            if raw is not None:
                missing = _collect_missing_hashes(raw, RESOLUTION_FULL)
                if not missing:
                    return raw
                for h in missing:
                    get_expr_from_network(node, h, RESOLUTION_SINGLE)
            else:
                sleep(interval)
        return get_expr_full_from_local_storage(node, expr_id)

    if resolution == RESOLUTION_LIST:
        return _poll_list()
    if resolution == RESOLUTION_FULL:
        return _poll_full()
    return _poll_single()


def put_expr_in_network(node, expr_id: bytes, payload_type: int) -> tuple[bool, str | None]:
    """Advertise an expression to the P2P network for peer retrieval.

    Determines the closest peer to ``expr_id`` in the DHT.  If the
    local node is the closest, indexes itself as the storage provider.
    Otherwise, sends a ``STORAGE_PUT`` advertisement to the closest
    peer so they know to fetch the expression from us.

    Args:
        node: A Node instance providing config and storage access.
        expr_id: The content hash of the expression to advertise.
        payload_type: The resolution strategy for the advertisement
            (e.g. ``RESOLUTION_SINGLE``, ``RESOLUTION_LIST``, etc.).

    Returns:
        A tuple of ``(success, error_message)``.  ``success`` is True
        if the advertisement was sent or self-indexed.  On failure
        ``error_message`` contains a description of the issue.
    """
    node_logger = node.logger
    expr_hex = expr_id.hex()
    try:
        from astreum.communication.storage_request.code import StorageRequestCode
        from astreum.communication.storage_request.model import StorageRequest
        from astreum.communication.models.message import Message, MessageTopic
        from astreum.communication.outgoing_queue import enqueue_outgoing
    except Exception as exc:
        node_logger.debug(
            "Communication module unavailable; cannot advertise expr %s: %s",
            expr_hex,
            exc,
        )
        return False, f"communication module unavailable: {exc}"
    try:
        provider_ip = node.relay_ip_address
        provider_port = node.config["port"]

    except Exception as exc:
        node_logger.debug("Unable to determine provider address for expr %s: %s", expr_hex, exc,)
        return False, f"unable to determine provider address: {exc}"

    try:
        provider_ip_bytes = socket.inet_aton(provider_ip)
        provider_port_bytes = int(provider_port).to_bytes(2, "big", signed=False)
        storage_key_bytes = node.config["storage_public_key_bytes"]
        relay_key_bytes = node.config["relay_public_key_bytes"]
    except Exception as exc:
        node_logger.debug("Unable to encode provider info for %s: %s", expr_hex, exc)
        return False, f"unable to encode provider info: {exc}"

    provider_payload = storage_key_bytes + relay_key_bytes + provider_ip_bytes + provider_port_bytes

    try:
        closest_peer = node.peer_route.closest_peer_for_hash(expr_id)
    except Exception as exc:
        node_logger.debug("Peer lookup failed for expr %s: %s", expr_hex, exc)
        return False, f"peer lookup failed: {exc}"

    is_self_closest = False
    if closest_peer is None or closest_peer.address is None:
        is_self_closest = True
    else:
        try:
            from astreum.communication.util import xor_distance
        except Exception as exc:
            node_logger.debug("Failed to import xor_distance for expr %s: %s", expr_hex, exc)
            is_self_closest = True
        else:
            try:
                self_distance = xor_distance(expr_id, node.config["storage_public_key_bytes"])
                peer_distance = xor_distance(expr_id, closest_peer.public_key_bytes)
            except Exception as exc:
                node_logger.debug("Failed computing distance for expr %s: %s", expr_hex, exc)
                is_self_closest = True
            else:
                is_self_closest = self_distance <= peer_distance

    if is_self_closest:
        node_logger.debug("Self is closest; indexing provider for expr %s", expr_hex)
        from astreum.storage.providers import provider_id_for_payload
        provider_id = provider_id_for_payload(node, provider_payload)
        node.storage_index[expr_id] = provider_id
        node_logger.debug("storage_index now has %d entries", len(node.storage_index))
        return True, None

    target_addr = closest_peer.address

    storage_req = StorageRequest(
        code=StorageRequestCode.STORAGE_PUT,
        data=provider_payload,
        expr_id=expr_id,
        payload_type=payload_type,
    )

    message_body = storage_req.to_bytes()

    message = Message(
        topic=MessageTopic.STORAGE_REQUEST,
        content=message_body,
        sender_public_key_bytes=node.storage_public_key_bytes,
    )
    message.encrypt(closest_peer.shared_key_bytes)
    try:
        queued = enqueue_outgoing(
            node,
            target_addr,
            message=message,
            difficulty=closest_peer.difficulty,
        )
        if queued:
            node_logger.debug(
                "Advertised expr %s to peer at %s:%s",
                expr_hex,
                target_addr[0],
                target_addr[1],
            )
        else:
            node_logger.debug(
                "Dropped expr advertisement %s to peer at %s:%s",
                expr_hex,
                target_addr[0],
                target_addr[1],
            )
            return False, "enqueue_outgoing dropped advertisement"
    except Exception as exc:
        node_logger.debug(
            "Failed to queue advertisement for expr %s to %s:%s",
            expr_hex,
            target_addr[0],
            target_addr[1],
            exc,
        )
        return False, f"failed to queue advertisement: {exc}"
    return True, None
