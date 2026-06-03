from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ....machine.models.expression import Expr, resolve_list_exprs
from ....machine.models.expression import ZERO32
from ....utils.integer import bytes_to_int, int_to_bytes


@dataclass
class StorageRecord:
    owner_public_key: bytes
    creation_block_hash: bytes
    last_payment_block_hash: bytes
    last_payment_winner: bytes
    total_bytes: int
    number_of_atoms: int
    _expr: Optional[Expr] = field(default=None, repr=False, compare=False)

    def to_expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        detail: Expr = Expr.Bytes(int_to_bytes(self.total_bytes))
        detail = Expr.Link(Expr.Link(head_hash=self.owner_public_key), detail)
        detail = Expr.Link(Expr.Bytes(int_to_bytes(self.number_of_atoms)), detail)
        detail = Expr.Link(Expr.Link(head_hash=self.last_payment_winner), detail)
        detail = Expr.Link(Expr.Link(head_hash=self.last_payment_block_hash), detail)
        detail = Expr.Link(Expr.Link(head_hash=self.creation_block_hash), detail)
        return detail

    def expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        self._expr = self.to_expr()
        return self._expr

    @classmethod
    def from_storage(cls, node: Any, head_hash: bytes) -> StorageRecord | None:
        header = node.get_expr_list(head_hash)
        if header is None or not isinstance(header, Expr.Link):
            return None
        nodes, missed = resolve_list_exprs(node, header)
        if missed:
            return None
        if len(nodes) != 6:
            return None
        record_fields = []
        for n in nodes:
            if isinstance(n, Expr.Bytes):
                record_fields.append(n.value)
            elif isinstance(n, Expr.Link) and n.head_hash is not None:
                record_fields.append(n.head_hash)
            else:
                return None
        return cls(
            creation_block_hash=record_fields[0],
            last_payment_block_hash=record_fields[1],
            last_payment_winner=record_fields[2],
            number_of_atoms=bytes_to_int(record_fields[3]),
            owner_public_key=record_fields[4],
            total_bytes=bytes_to_int(record_fields[5]),
        )
