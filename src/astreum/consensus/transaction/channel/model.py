from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ....machine.models.expression import Expr, resolve_list_exprs
from ....machine.models.expression import ZERO32
from ....utils.integer import bytes_to_int, int_to_bytes


@dataclass
class Channel:
    balance: int
    counter: int
    withdrawal_window: bytes
    _expr: Optional[Expr] = field(default=None, repr=False, compare=False)

    def to_expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        detail: Expr = Expr.Bytes(self.withdrawal_window)
        detail = Expr.Link(Expr.Bytes(int_to_bytes(self.counter)), detail)
        detail = Expr.Link(Expr.Bytes(int_to_bytes(self.balance)), detail)
        return detail

    def expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        self._expr = self.to_expr()
        return self._expr

    @classmethod
    def from_storage(cls, node: Any, head_hash: bytes) -> Channel | None:
        if not head_hash or head_hash == ZERO32:
            return None
        header = node.get_expr_list(head_hash)
        if header is None or not isinstance(header, Expr.Link):
            return None
        nodes, missed = resolve_list_exprs(node, header)
        if missed:
            return None
        if len(nodes) != 3:
            return None
        balance = bytes_to_int(nodes[0].value)
        counter = bytes_to_int(nodes[1].value)
        withdrawal_window = nodes[2].value
        return cls(
            balance=balance,
            counter=counter,
            withdrawal_window=withdrawal_window,
        )
