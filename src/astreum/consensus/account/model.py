from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from astreum.expression import Expr, NIL, link, int_
from astreum.storage.radix import RadixTree, clone_radix_tree, get_radix_node_expr, put_in_radix_tree


@dataclass
class Account:
    balance: int
    code_hash: bytes
    counter: int
    data_hash: bytes
    channels_hash: bytes
    data: RadixTree
    channels: RadixTree
    _expr: Optional["Expr"] = field(default=None, repr=False)

    def to_expr(self) -> "Expr":
        detail: Expr = link(int_(self.balance), NIL)
        detail = link(Expr("link", head_hash=self.channels_hash), detail)
        detail = link(Expr("link", head_hash=self.code_hash), detail)
        detail = link(int_(self.counter), detail)
        detail = link(Expr("link", head_hash=self.data_hash), detail)
        return detail

    def expr(self) -> "Expr":
        if self._expr is not None:
            return self._expr
        self._expr = self.to_expr()
        return self._expr

    def clone(self) -> "Account":
        cloned = Account(
            balance=self.balance,
            code_hash=self.code_hash,
            counter=self.counter,
            data_hash=self.data_hash,
            channels_hash=self.channels_hash,
            data=clone_radix_tree(self.data),
            channels=clone_radix_tree(self.channels),
        )
        if self._expr is not None:
            cloned._expr = self._expr
        return cloned


def extract_account_exprs(account: Account) -> list[Expr]:
    """Collect every expr that must be in storage to reconstruct an Account."""
    exprs: list[Expr] = [account.expr()]
    for node in account.data.nodes.values():
        exprs.append(get_radix_node_expr(node))
        val = node.value
        if val is not None and not isinstance(val, bytes):
            exprs.append(val)
    for node in account.channels.nodes.values():
        exprs.append(get_radix_node_expr(node))
        val = node.value
        if val is not None and not isinstance(val, bytes):
            exprs.append(val)
    return exprs


def generate_new_account_storage_contracts(
    node: Any,
    block: Any,
    storage_account: Account,
    expr: Expr,
) -> None:
    """Generate storage contract and register in storage data."""
    from astreum.consensus.transaction.storage.initial import generate_initial_storage_record
    from astreum.storage.records import put_record_in_cold_storage

    result = generate_initial_storage_record(node, block, expr)
    if result is None:
        return
    record, slot_map, _, _ = result
    put_in_radix_tree(storage_account.data, node, expr.hash(), record.expr())
    for h, slot in slot_map.items():
        put_in_radix_tree(storage_account.data, node, h, slot.expr())
    storage_account.data_hash = storage_account.data.root_hash
    put_record_in_cold_storage(node, expr.hash(), list(slot_map.keys()))
    block.pending_exprs.append(record.expr())
    for slot in slot_map.values():
        block.pending_exprs.append(slot.expr())
    block.pending_exprs.append(expr)
