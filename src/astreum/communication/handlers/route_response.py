from __future__ import annotations

from typing import Sequence

import socket

from ..models.message import Message

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .... import Node


def handle_route_response(node: "Node", addr: Sequence[object], message: Message) -> None:
    logger = node.logger

    payload = message.content
    if not payload:
        return
    host_len = 16 if node.use_ipv6 else 4
    chunk_size = host_len + 2
    if len(payload) % chunk_size != 0:
        logger.warning(
            "ROUTE_RESPONSE payload size mismatch (%s bytes) from %s",
            len(payload),
            addr,
        )
        return

    decoded_addresses = []
    family = socket.AF_INET6 if node.use_ipv6 else socket.AF_INET
    for index in range(0, len(payload), chunk_size):
        host_bytes = payload[index : index + host_len]
        port_bytes = payload[index + host_len : index + chunk_size]
        try:
            host = socket.inet_ntop(family, host_bytes)
        except OSError as exc:
            logger.warning(
                "Invalid host bytes in ROUTE_RESPONSE from %s: %s",
                addr,
                exc,
            )
            continue
        port = int.from_bytes(port_bytes, "big", signed=False)
        decoded_addresses.append((host, port))
    if not decoded_addresses:
        return
    logger.debug("Decoded %s addresses from ROUTE_RESPONSE", len(decoded_addresses))

    handshake_message = Message(handshake=True, sender=node.relay_public_key)
    for host, port in decoded_addresses:
        node.outgoing_queue.put((handshake_message.to_bytes(), (host, port)))
