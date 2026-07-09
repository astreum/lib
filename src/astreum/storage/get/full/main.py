from __future__ import annotations

from typing import Optional

from astreum.expression import Expr
from astreum.storage.get.single import get_expr


def get_expr_full(node, expr_id: bytes) -> Optional[Expr]:
    """Resolve an Expr and all transitive link hashes using full resolution.

    Fetches the root expression, then recursively resolves every
    ``_head_hash`` / ``_tail_hash`` using the same resolution chain
    (hot → cold → network).  Returns a fully materialized expression
    tree with no remaining hash references.

    Args:
        node: A Node instance providing config and storage access.
        expr_id: The content hash of the root expression.

    Returns:
        The fully resolved Expr with all links expanded inline, or None
        if any part of the tree cannot be found.
    """
    expr = get_expr(node, expr_id)
    if expr is None:
        return None
    if not expr._tag == "link":
        return expr

    if expr._head is None and expr._head_hash is not None:
        head = get_expr_full(node, expr._head_hash)
        if head is None:
            return None
        expr._head = head
        expr._head_hash = None

    if expr._tail is None and expr._tail_hash is not None:
        tail = get_expr_full(node, expr._tail_hash)
        if tail is None:
            return None
        expr._tail = tail
        expr._tail_hash = None

    return expr
