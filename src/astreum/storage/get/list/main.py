from __future__ import annotations

from typing import Optional, Union

from astreum.expression import Expr
from astreum.storage.get.single import get_expr


def get_expr_list(node, root: Union[bytes, Expr]) -> Optional[Expr]:
    """Resolve an Expr and its tail chain using full resolution.

    Fetches the root expression, then walks the ``_tail`` pointers,
    resolving each unresolved ``_tail_hash`` using the same resolution
    chain (hot → cold → network).  Returns a fully materialized list
    with no remaining hash references.

    Args:
        node: A Node instance providing config and storage access.
        root: The content hash of the root expression, or an Expr
            instance that has already been fetched.

    Returns:
        The root Expr with the tail chain expanded inline, or None
        if any part of the chain cannot be found.
    """
    if isinstance(root, Expr):
        expr = root
    else:
        expr = get_expr(node, root)
        if expr is None:
            return None

    current = expr
    while current is not None and current._tag == "link":
        if current._tail_hash is not None:
            resolved = get_expr(node, current._tail_hash)
            if resolved is None:
                return None
            current._tail = resolved
            current._tail_hash = None
        current = current._tail
    return expr
