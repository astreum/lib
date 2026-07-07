from __future__ import annotations

from time import time
from typing import Optional


def get_expr_from_hot_storage(node, expr_id: bytes) -> Optional["Expr"]:
    """Retrieve an Expr from the in-memory hot storage cache.

    Looks up ``expr_id`` in the node's hot storage dict and refreshes
    the access timestamp on a hit.

    Args:
        node: A Node instance providing config and storage access.
        expr_id: The content hash of the expression to retrieve.

    Returns:
        The cached Expr if found, or None.
    """
    with node.hot_storage_lock:
        expr = node.hot_storage.get(expr_id)
        if expr is not None:
            node.hot_storage_timestamps[expr_id] = time()
            return expr
        return None
