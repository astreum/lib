from __future__ import annotations

from ...machine.models.expression import Expr, NIL, ZERO32, link
from .node import BloomNode
from ..bloom_filter.main import BloomFilter
from ..bloom_filter.expr import bloom_to_expr as _filter_to_expr, bloom_from_expr as _filter_from_expr


def _ref(value: bytes | None) -> Expr:
    """NIL when None, Link(head_hash=value) when set."""
    return NIL if value is None else Expr("link", head_hash=value)


def bloom_node_to_expr(node: BloomNode) -> Expr:
    """Serialize a BloomNode to an Expr.

    Format: Link(block_ref, Link(left_ref, Link(right_ref, Link(bloom_filter, NIL))))
    Each ref = NIL when absent, Link(head_hash=hash) when set.
    """
    block_ref = _ref(node.start_hash)
    left_ref = _ref(node.left.to_expr().hash() if node.left else None)
    right_ref = _ref(node.right.to_expr().hash() if node.right else None)
    filter_expr = _filter_to_expr(node.filter)

    return link(
        block_ref,
        link(
            left_ref,
            link(
                right_ref,
                link(
                    filter_expr,
                    NIL,
                ),
            ),
        ),
    )


def bloom_node_from_expr(expr: Expr) -> BloomNode:
    """Deserialize a BloomNode from an Expr."""
    # Link(block_ref, Link(left_ref, Link(right_ref, Link(filter, NIL))))
    block_ref = expr._head
    left_ref = expr._tail._head
    right_ref = expr._tail._tail._head
    filter_expr = expr._tail._tail._tail._head

    # Extract hashes
    start_hash = None if (block_ref is None or block_ref is NIL) else block_ref._head_hash
    left_hash = None if (left_ref is None or left_ref is NIL) else left_ref._head_hash
    right_hash = None if (right_ref is None or right_ref is NIL) else right_ref._head_hash

    # Deserialize filter
    bf = _filter_from_expr(filter_expr)

    # Determine level from children presence
    is_leaf = left_hash is None and right_hash is None

    node = BloomNode(level=10 if is_leaf else 0)
    node.filter = bf
    node.start_hash = start_hash
    node._left_hash = left_hash
    node._right_hash = right_hash

    # Children are materialized by caller via node_get if needed
    return node
