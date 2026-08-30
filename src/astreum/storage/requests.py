from __future__ import annotations

from threading import RLock
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from astreum import Node


def add_expr_req(node: "Node", expr_id: bytes, payload_type: Optional[int] = None) -> None:
    """Mark an expr request as pending with an optional payload type.

    Args:
        node: A Node instance with the ``expr_requests`` registry.
        expr_id: The content hash of the pending request.
        payload_type: The resolution strategy attached to the request,
            or ``None``.
    """
    with node.expr_requests_lock:
        node.expr_requests[expr_id] = payload_type


def has_expr_req(node: "Node", expr_id: bytes) -> bool:
    """Return True if the expr request is currently tracked.

    Args:
        node: A Node instance with the ``expr_requests`` registry.
        expr_id: The content hash of the request to check.

    Returns:
        True if a pending request exists for ``expr_id``.
    """
    with node.expr_requests_lock:
        return expr_id in node.expr_requests


def pop_expr_req(node: "Node", expr_id: bytes) -> Optional[int]:
    """Remove the pending request if present and return its payload type.

    Args:
        node: A Node instance with the ``expr_requests`` registry.
        expr_id: The content hash of the request to remove.

    Returns:
        The payload type the request was registered with, or ``None``
        if no pending request exists.
    """
    with node.expr_requests_lock:
        return node.expr_requests.pop(expr_id, None)


def get_expr_req_payload(node: "Node", expr_id: bytes) -> Optional[int]:
    """Return the payload type for a pending request without removing it.

    Args:
        node: A Node instance with the ``expr_requests`` registry.
        expr_id: The content hash of the pending request.

    Returns:
        The payload type the request is registered with, or ``None``
        if no pending request exists.
    """
    with node.expr_requests_lock:
        return node.expr_requests.get(expr_id)
