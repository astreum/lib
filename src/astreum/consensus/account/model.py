from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ...machine.models.expression import Expr, link, int_
from ...storage.models.trie import Trie


@dataclass
class Account:
    balance: int
    code_hash: bytes
    counter: int
    data_hash: bytes
    channels_hash: bytes
    data: Trie
    channels: Trie
    _expr: Optional["Expr"] = field(default=None, repr=False)

    def to_expr(self) -> "Expr":
        # Body Link chain from innermost to outermost (alphabetical field order).
        detail: Expr = int_(self.balance)
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
            balance=int(self.balance),
            code_hash=bytes(self.code_hash),
            counter=int(self.counter),
            data_hash=bytes(self.data_hash),
            channels_hash=bytes(self.channels_hash),
            data=self.data.clone(),
            channels=self.channels.clone(),
        )
        if self._expr is not None:
            cloned._expr = self._expr
        return cloned


def extract_account_exprs(account: Account) -> list[Expr]:
    """Collect every expr that must be in storage to reconstruct an Account."""
    exprs: list[Expr] = [account.expr()]
    for node in account.data.nodes.values():
        exprs.append(node.expr())
        val = node.value
        if val is not None and not isinstance(val, bytes):
            exprs.append(val)
    for node in account.channels.nodes.values():
        exprs.append(node.expr())
        val = node.value
        if val is not None and not isinstance(val, bytes):
            exprs.append(val)
    return exprs


def generate_new_account_storage_contracts(
    node: Any,
    block: Any,
    burn_account: Account,
    expr: Expr,
) -> None:
    """Generate storage contract for an account expr and register in burn data."""
    from ...consensus.transaction.storage.initial import generate_initial_storage_record

    result = generate_initial_storage_record(node, block, expr)
    if result is None:
        return
    record, slot_map, _, _ = result
    burn_account.data.put(node, expr.hash(), record.expr())
    for h, slot in slot_map.items():
        burn_account.data.put(node, h, slot.expr())
    burn_account.data_hash = burn_account.data.root_hash
    block.pending_exprs.append(record.expr())
    for slot in slot_map.values():
        block.pending_exprs.append(slot.expr())
    block.pending_exprs.append(expr)
