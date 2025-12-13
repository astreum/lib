from __future__ import annotations

import socket

from ..models.message import Message, MessageTopic
from ..util import xor_distance

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .... import Node
    from ..models.peer import Peer


def handle_route_request(node: "Node", peer: "Peer", message: Message) -> None:
    sender_public_key = getattr(peer, "public_key_bytes", None)
    if not sender_public_key:
        node.logger.warning("Unknown sender for ROUTE_REQUEST from %s", peer.address)
        return

    if not message.content:
        node.logger.warning("ROUTE_REQUEST missing route id from %s", peer.address)
        return
    route_id = message.content[0]
    if route_id == 0:
        route = node.peer_route
    elif route_id == 1:
        route = node.validation_route
        if route is None:
            node.logger.warning("Validation route not initialized for %s", peer.address)
            return
    else:
        node.logger.warning("Unknown route id %s in ROUTE_REQUEST from %s", route_id, peer.address)
        return

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

        bucket_peer = node.get_peer(closest_key)
        if bucket_peer is None or bucket_peer.address is None:
            continue

        host, port = bucket_peer.address
        try:
            address_bytes = socket.inet_pton(socket.AF_INET, host)
        except OSError:
            try:
                address_bytes = socket.inet_pton(socket.AF_INET6, host)
            except OSError as exc:
                node.logger.warning("Invalid peer address %s: %s", bucket_peer.address, exc)
                continue

        port_bytes = int(port).to_bytes(2, "big", signed=False)
        payload_parts.append(address_bytes + port_bytes)

    response = Message(
        topic=MessageTopic.ROUTE_RESPONSE,
        content=b"".join(payload_parts),
        sender=node.relay_public_key,
    )
    response.encrypt(peer.shared_key_bytes)
    node.outgoing_queue.put((response.to_bytes(), peer.address))
