from __future__ import annotations

from threading import RLock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .. import Node


def add_atom_req(node: "Node", atom_id: bytes) -> None:
    """Mark an atom request as pending."""
    with node.atom_requests_lock:
        node.atom_requests.add(atom_id)


def has_atom_req(node: "Node", atom_id: bytes) -> bool:
    """Return True if the atom request is currently tracked."""
    with node.atom_requests_lock:
        return atom_id in node.atom_requests


def pop_atom_req(node: "Node", atom_id: bytes) -> bool:
    """Remove the pending request if present. Returns True when removed."""
    with node.atom_requests_lock:
        if atom_id in node.atom_requests:
            node.atom_requests.remove(atom_id)
            return True
        return False
