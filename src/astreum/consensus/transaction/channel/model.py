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
    withdrawal_window: int
    _expr: Optional[Expr] = field(default=None, repr=False, compare=False)

    def to_expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        detail: Expr = Expr.Symbol("channel")
        detail = Expr.Link(
            Expr.Bytes(
                int.to_bytes(
                    self.withdrawal_window, 8, "little", signed=False
                )
            ),
            detail,
        )
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
        if len(nodes) != 4:
            return None
        terminal = nodes[-1]
        if not isinstance(terminal, Expr.Symbol) or terminal.value != "channel":
            return None
        fields = []
        for n in nodes[:-1]:
            if isinstance(n, Expr.Bytes):
                fields.append(bytes_to_int(n.value))
            else:
                return None
        if len(fields) != 3:
            return None
        return cls(
            balance=fields[0],
            counter=fields[1],
            withdrawal_window=fields[2],
        )
