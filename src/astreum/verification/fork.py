from __future__ import annotations

from typing import Any, Dict, Optional

from astreum.validation.models.fork import Fork


def load_forks(node: Any, data: Any) -> Dict[bytes, Fork]:
    """Load forks from fork dicts into node.forks."""
    for fork_data in data:
        fork = Fork.from_dict(fork_data)
        node.forks[fork.head] = fork

    return node.forks


def export_forks(node: Any) -> list[dict[str, Any]]:
    """Export node.forks as a list of fork dicts."""
    return [fork.to_dict() for fork in node.forks.values()]
