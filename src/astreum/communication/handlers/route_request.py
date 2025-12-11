from __future__ import annotations

from typing import Sequence

import socket

from ..models.message import Message, MessageTopic
from ..util import xor_distance

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .... import Node


def handle_route_request(node: "Node", addr: Sequence[object], message: Message) -> None:
    logger = node.logger

    request_addr = (addr[0], int(addr[1])) if len(addr) >= 2 else addr
    sender_public_key = node.addresses.get(request_addr)
    if not sender_public_key:
        logger.warning("Unknown sender for ROUTE_REQUEST from %s", addr)
        return

    if not message.content:
        logger.warning("ROUTE_REQUEST missing route id from %s", addr)
        return
    route_id = message.content[0]
    if route_id == 0:
        route = node.peer_route
    elif route_id == 1:
        route = node.validation_route
        if route is None:
            logger.warning("Validation route not initialized for %s", addr)
            return
    else:
        logger.warning("Unknown route id %s in ROUTE_REQUEST from %s", route_id, addr)
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
        peer = node.peers.get(closest_key)
        if not peer or not peer.address:
            continue
        host, port = peer.address
        try:
            address_bytes = socket.inet_pton(socket.AF_INET, host)
        except OSError:
            try:
                address_bytes = socket.inet_pton(socket.AF_INET6, host)
            except OSError as exc:
                logger.warning("Invalid peer address %s: %s", peer.address, exc)
                continue
        port_bytes = int(port).to_bytes(2, "big", signed=False)
        payload_parts.append(address_bytes + port_bytes)

    response = Message(
        topic=MessageTopic.ROUTE_RESPONSE,
        content=b"".join(payload_parts),
        sender=node.relay_public_key,
    )
    try:
        request_host, request_port = addr[0], int(addr[1])
    except Exception:
        logger.warning("Invalid requester address %s", addr)
        return
    node.outgoing_queue.put((response.to_bytes(), (request_host, request_port)))
