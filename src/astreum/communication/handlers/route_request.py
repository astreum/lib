from __future__ import annotations

import socket

from astreum.communication.outgoing_queue import enqueue_outgoing
from astreum.communication.models.message import Message, MessageTopic
from astreum.communication.models.peer import get_peer
from astreum.communication.util import xor_distance

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from astreum import Node
    from astreum.communication.models.peer import Peer


def handle_route_request(node: "Node", peer: "Peer", message: Message) -> tuple[bool, str | None]:
    sender_public_key = getattr(peer, "public_key_bytes", None)
    if not sender_public_key:
        node.logger.debug("Unknown sender for ROUTE_REQUEST from %s", peer.address)
        return False, "unknown sender"

    if not message.content:
        node.logger.debug("ROUTE_REQUEST missing route id from %s", peer.address)
        return False, "missing route id"
    route_id = message.content[0]
    if route_id == 0:
        route = node.peer_route
    elif route_id == 1:
        route = node.validation_route
        if route is None:
            node.logger.debug("Validation route not initialized for %s", peer.address)
            return False, "validation route not initialized"
    else:
        node.logger.debug("Unknown route id %s in ROUTE_REQUEST from %s", route_id, peer.address)
        return False, f"unknown route id {route_id}"

    payload_parts = []
    for bucket in route.buckets.values():
        closest_key = None
        closest_distance = None

        for peer_key in bucket:
            try:
                distance = xor_distance(sender_public_key, peer_key)
            except ValueError:
                continue

            if closest_distance is None or distance < closest_distance:
                closest_distance = distance
                closest_key = peer_key

        if closest_key is None:
            continue

        bucket_peer = get_peer(node, closest_key)
        if bucket_peer is None or bucket_peer.address is None:
            continue

        host, port = bucket_peer.address
        try:
            address_bytes = socket.inet_pton(socket.AF_INET, host)
        except OSError:
            try:
                address_bytes = socket.inet_pton(socket.AF_INET6, host)
            except OSError as exc:
                node.logger.debug("Invalid peer address %s: %s", bucket_peer.address, exc)
                continue

        port_bytes = int(port).to_bytes(2, "big", signed=False)
        payload_parts.append(address_bytes + port_bytes)

    response = Message(
        topic=MessageTopic.ROUTE_RESPONSE,
        content=b"".join(payload_parts),
        sender_public_key_bytes=node.storage_public_key_bytes,
    )
    response.encrypt(peer.shared_key_bytes)
    enqueue_outgoing(
        node,
        peer.address,
        message=response,
        difficulty=peer.difficulty,
    )
    return True, None
