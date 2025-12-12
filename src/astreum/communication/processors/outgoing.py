from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from .. import Node

def process_outgoing_messages(node: "Node") -> None:
    """Send queued outbound packets."""
    while True:
        try:
            payload, addr = node.outgoing_queue.get()
        except Exception:
            node.logger.exception("Error taking from outgoing queue")
            continue

        try:
            node.outgoing_socket.sendto(payload, addr)
        except Exception as exc:
            node.logger.warning("Error sending message to %s: %s", addr, exc)
