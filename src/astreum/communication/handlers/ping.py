from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Sequence

from ..models.ping import Ping

if TYPE_CHECKING:
    from .... import Node


def handle_ping(node: "Node", addr: Sequence[object], payload: bytes) -> None:
    """Update peer and validation state based on an incoming ping message."""
    logger = node.logger
    try:
        host, port = addr[0], int(addr[1])
    except Exception:
        return

    address_key = (host, port)
    sender_public_key_bytes = node.addresses.get(address_key)
    if sender_public_key_bytes is None:
        return

    peer = node.peers.get(sender_public_key_bytes)
    if peer is None:
        return

    try:
        ping = Ping.from_bytes(payload)
    except Exception as exc:
        logger.warning("Error decoding ping: %s", exc)
        return

    peer.timestamp = datetime.now(timezone.utc)
    peer.latest_block = ping.latest_block

    validation_route = node.validation_route
    if validation_route is None:
        return

    try:
        if ping.is_validator:
            validation_route.add_peer(sender_public_key_bytes)
        else:
            validation_route.remove_peer(sender_public_key_bytes)
    except Exception:
        pass
