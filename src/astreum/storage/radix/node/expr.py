from __future__ import annotations

from ....machine.models.expression import Expr, NIL, link, int_, bytes_
from .model import RadixNode


def convert_radix_node_to_expr(node: RadixNode) -> Expr:
    """Serialize a RadixNode into an S-expression for persistent storage.

    Encodes the node's key, key length, children (child_0, child_1),
    and value into a chain of nested (link ...) expressions.

    Args:
        node: The radix node to serialize.

    Returns:
        An Expr representing the node.
    """
    if node.value is None:
        expr = link(NIL, NIL)
    elif isinstance(node.value, bytes):
        expr = Expr("link", head_hash=node.value, tail=NIL)
    else:
        expr = link(node.value, NIL)

    expr = Expr("link", head_hash=node.child_1, tail=expr) if node.child_1 else link(NIL, expr)
    expr = Expr("link", head_hash=node.child_0, tail=expr) if node.child_0 else link(NIL, expr)
    expr = link(bytes_(node.key), expr)
    expr = link(int_(node.key_len), expr)
    return expr


def get_radix_node_expr(node: RadixNode) -> Expr:
    if node._expr is None:
        node._expr = convert_radix_node_to_expr(node)
    return node._expr
