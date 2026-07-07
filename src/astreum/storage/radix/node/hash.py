from __future__ import annotations

from typing import Optional

from ....machine.models.expression import Expr
from .model import RadixNode


def radix_node_hash(node: RadixNode) -> bytes:
    if node._hash is None:
        from .expr import convert_radix_node_to_expr
        node._hash = convert_radix_node_to_expr(node).hash()
    return node._hash


def invalidate_radix_node_cache(node: RadixNode) -> None:
    node._hash = None
    node._expr = None
