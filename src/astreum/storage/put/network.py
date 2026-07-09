from __future__ import annotations

import socket


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
            "Failed to queue advertisement for expr %s to %s:%s: %s",
            expr_hex,
            target_addr[0],
            target_addr[1],
            exc,
        )
        return False, f"failed to queue advertisement: {exc}"
    return True, None