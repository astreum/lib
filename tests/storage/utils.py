from __future__ import annotations

from astreum.machine.models.expression import Expr, int_, exprs_to_linked_expr


def generate_nearest_expr(
    source_key: bytes,
    target_key: bytes,
    *,
    value: int = 0,
) -> Expr:
    """Create a simple expr (int atom) for testing.

    The expr itself is a plain int atom — XOR-distance logic is handled by the
    caller (advertisement / peer routing) based on source_key / target_key.
    """
    return int_(value)


def generate_nearest_expr_list(
    source_key: bytes,
    target_key: bytes,
    *,
    list_size: int = 4,
) -> Expr:
    """Create a linked list of *list_size* int atoms for testing."""
    items = [int_(i) for i in range(list_size)]
    return exprs_to_linked_expr(items)
