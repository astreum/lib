from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ..models.ping import Ping
from ..models.peer import Peer

if TYPE_CHECKING:
    from .... import Node


def handle_ping(node: "Node", peer: Peer, payload: bytes) -> None:
    """Update peer and validation state based on an incoming ping message."""
    try:
        ping = Ping.from_bytes(payload)
    except Exception as exc:
        node.logger.warning("Error decoding ping: %s", exc)
        return

    peer.timestamp = datetime.now(timezone.utc)
    peer.latest_block = ping.latest_block

    validation_route = node.validation_route
    if validation_route is None:
        return

    try:
        if ping.is_validator:
            validation_route.add_peer(peer.public_key_bytes)
        else:
            validation_route.remove_peer(peer.public_key_bytes)
    except Exception:
        pass
