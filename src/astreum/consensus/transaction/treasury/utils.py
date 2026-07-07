from __future__ import annotations

from ....storage.radix import RadixTree, get_radix_node_expr
from ....machine.models.expression import Expr
from .record import TreasuryLoanRecord


def _collect_sub_exprs(expr: Expr) -> list:
    """Walk an expr tree and collect all sub-expressions without resolving hashes."""
    result = [expr]
    if expr._tag == "link":
        if expr._head is not None:
            result.extend(_collect_sub_exprs(expr._head))
        if expr._tail is not None:
            result.extend(_collect_sub_exprs(expr._tail))
    return result


def _trie_exprs(trie: RadixTree) -> list:
    emitted: list = []
    if not trie.nodes:
        return emitted
    for node_hash in sorted(trie.nodes.keys()):
        trie_node = trie.nodes[node_hash]
        expr = get_radix_node_expr(trie_node)
        if expr.hash() != node_hash:
            continue
        emitted.extend(_collect_sub_exprs(expr))
    return emitted


def _paid_payment_count(loan: TreasuryLoanRecord) -> int | None:
    if loan.next_payment_block_number == 0:
        return loan.payment_count
    if loan.payment_interval_blocks <= 0:
        return None
    paid_span = loan.next_payment_block_number - loan.creation_block_number
    if paid_span <= 0 or paid_span % loan.payment_interval_blocks != 0:
        return None
    return (paid_span // loan.payment_interval_blocks) - 1


def _remaining_payment_count(loan: TreasuryLoanRecord) -> int | None:
    total_payment_count = loan.payment_count
    paid_payment_count = _paid_payment_count(loan)
    if total_payment_count is None or paid_payment_count is None:
        return None
    remaining = total_payment_count - paid_payment_count
    if remaining < 0:
        return None
    return remaining


def _interest_paid_delta(
    *,
    loan: TreasuryLoanRecord,
    paid_before: int,
    paid_after: int,
    total_payment_count: int,
) -> int | None:
    scheduled_total = loan.payment_amount * total_payment_count
    total_interest = scheduled_total - loan.discounted_amount
    if total_interest < 0:
        return None
    interest_before = total_interest * paid_before // total_payment_count
    interest_after = total_interest * paid_after // total_payment_count
    return interest_after - interest_before
