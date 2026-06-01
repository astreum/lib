from __future__ import annotations

from ...machine.models.expression import Expr, NIL
from ...utils.integer import int_to_bytes
from .main import BloomFilter


def bloom_to_expr(bf: BloomFilter) -> Expr:
    """Serialize a BloomFilter to an Expr. Outer Link uses start_hash as head_hash."""
    tiers: Expr = NIL
    for tier in reversed(bf.tiers):
        tiers = Expr.Link(Expr.Bytes(bytes(tier)), tiers)

    return Expr.Link(
        head_hash=bf.start_hash,
        tail=Expr.Link(
            Expr.Bytes(int_to_bytes(bf.count)),
            tiers,
        ),
    )


def bloom_from_expr(expr: Expr) -> BloomFilter:
    """Deserialize a BloomFilter from an Expr."""
    start_hash = expr.head_hash
    count = int.from_bytes(expr.tail.head.value, "big")

    tiers: list[bytearray] = []
    current = expr.tail.tail
    while isinstance(current, Expr.Link):
        tiers.append(bytearray(current.head.value))
        current = current.tail
    if isinstance(current, Expr.Bytes):
        tiers.append(bytearray(current.value))

    bf = BloomFilter()
    bf.count = count
    bf.tiers = tiers
    bf.start_hash = start_hash
    return bf
