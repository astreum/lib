from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .. import Node


def message_difficulty(node: "Node") -> int:
    """Compute current message difficulty based on incoming queue pressure."""
    base = 1
    try:
        size = int(getattr(node, "incoming_queue_size", 0) or 0)
        limit = int(getattr(node, "incoming_queue_size_limit", 0) or 0)
    except Exception:
        return base

    if limit <= 0:
        return base

    pressure = size / limit
    if pressure < 0.5:
        value = base
    elif pressure < 0.75:
        value = base + 1
    elif pressure < 0.9:
        value = base + 2
    else:
        value = base + 3

    return max(1, min(255, int(value)))
