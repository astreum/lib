from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ....machine.models.expression import Expr, resolve_list_exprs
from ....machine.models.expression import ZERO32


@dataclass
class Channel:
    balance: int
    counter: int
    withdrawal_window: int
    _expr: Optional[Expr] = field(default=None, repr=False, compare=False)

    def to_expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        detail: Expr = Expr.Int(self.withdrawal_window)
        detail = Expr.Link(Expr.Int(self.counter), detail)
        detail = Expr.Link(Expr.Int(self.balance), detail)
        return detail

    def expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        self._expr = self.to_expr()
        return self._expr

    @classmethod
    def from_storage(cls, node, head_hash: bytes) -> Optional["Channel"]:
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
        if not isinstance(nodes[0], Expr.Int):
            return None
        if not isinstance(nodes[1], Expr.Int):
            return None
        if not isinstance(nodes[2], Expr.Int):
            return None
        return cls(
            balance=nodes[0].value,
            counter=nodes[1].value,
            withdrawal_window=nodes[2].value,
        )
