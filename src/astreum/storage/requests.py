from __future__ import annotations

from threading import RLock
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .. import Node


def add_atom_req(node: "Node", atom_id: bytes, payload_type: Optional[int] = None) -> None:
    """Mark an atom request as pending with an optional payload type."""
    with node.atom_requests_lock:
        node.atom_requests[atom_id] = payload_type


def has_atom_req(node: "Node", atom_id: bytes) -> bool:
    """Return True if the atom request is currently tracked."""
    with node.atom_requests_lock:
        return atom_id in node.atom_requests


def pop_atom_req(node: "Node", atom_id: bytes) -> Optional[int]:
    """Remove the pending request if present and return its payload type."""
    with node.atom_requests_lock:
        return node.atom_requests.pop(atom_id, None)


def get_atom_req_payload(node: "Node", atom_id: bytes) -> Optional[int]:
    """Return the payload type for a pending request without removing it."""
    with node.atom_requests_lock:
        return node.atom_requests.get(atom_id)
