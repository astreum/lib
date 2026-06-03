from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ...machine.models.expression import Expr
from ...storage.models.trie import Trie
from ...utils.integer import int_to_bytes


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
        detail: Expr = Expr.Bytes(int_to_bytes(self.balance))
        detail = Expr.Link(Expr.Link(head_hash=self.channels_hash), detail)
        detail = Expr.Link(Expr.Link(head_hash=self.code_hash), detail)
        detail = Expr.Link(Expr.Bytes(int_to_bytes(self.counter)), detail)
        detail = Expr.Link(Expr.Link(head_hash=self.data_hash), detail)
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
