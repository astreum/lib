from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ....machine.models.expression import Expr, NIL, resolve_list_exprs
from ....machine.models.expression import ZERO32
from ....utils.integer import bytes_to_int, int_to_bytes


@dataclass
class StorageRecord:
    creation_block_hash: bytes = b""
    last_payment_block_hash: bytes = b""
    last_payment_winner: bytes = b""
    new_size: int = 0
    new_count: int = 0
    _expr: Optional[Expr] = field(default=None, repr=False, compare=False)

    def to_expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        # Permanent core (innermost to outermost)
        tail: Expr = Expr.Bytes(int_to_bytes(self.new_size))
        tail = Expr.Link(Expr.Bytes(int_to_bytes(self.new_count)), tail)
        tail = Expr.Link(Expr.Link(head_hash=self.creation_block_hash), tail)
        # Transient wrapper (rewritten each payment — only 2 new Links)
        tail = Expr.Link(Expr.Link(head_hash=self.last_payment_winner), tail)
        tail = Expr.Link(Expr.Link(head_hash=self.last_payment_block_hash), tail)
        return tail

    def expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        self._expr = self.to_expr()
        return self._expr

    @staticmethod
    def _extract_hash(n: Expr) -> bytes:
        """Extract the stored hash from a node, whether resolved or not."""
        if isinstance(n, Expr.Link):
            if n.head_hash is not None:
                return n.head_hash
            if n.head is not None:
                return n.head.hash()
        return ZERO32

    @classmethod
    def from_storage(cls, node: Any, expr_id: bytes) -> StorageRecord | None:
        header = node.get_expr(expr_id)
        if header is None or not isinstance(header, Expr.Link):
            return None
        nodes, missed = resolve_list_exprs(node, header)
        if missed:
            return None
        if len(nodes) != 5:
            return None
        # nodes[0-2]: Link hash pointers
        if not all(isinstance(n, Expr.Link) for n in nodes[:3]):
            return None
        # nodes[3-4]: Bytes ints
        if not all(isinstance(n, Expr.Bytes) for n in nodes[3:5]):
            return None
        obj = cls(
            last_payment_block_hash=cls._extract_hash(nodes[0]),
            last_payment_winner=cls._extract_hash(nodes[1]),
            creation_block_hash=cls._extract_hash(nodes[2]),
            new_count=bytes_to_int(nodes[3].value),
            new_size=bytes_to_int(nodes[4].value),
        )
        obj._expr = header
        return obj


@dataclass
class StorageSlot:
    record_hash: bytes
    sequence: int
    _expr: Optional[Expr] = field(default=None, repr=False, compare=False)

    def to_expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        return Expr.Link(
            head_hash=self.record_hash,
            tail=Expr.Bytes(int_to_bytes(self.sequence)),
        )

    def expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        self._expr = self.to_expr()
        return self._expr

    @classmethod
    def from_storage(cls, node: Any, expr_id: bytes) -> StorageSlot | None:
        expr = node.get_expr(expr_id)
        if not isinstance(expr, Expr.Link):
            return None
        if expr.head_hash is None:
            return None
        tail = expr.tail
        if not isinstance(tail, Expr.Bytes):
            return None
        obj = cls(
            record_hash=expr.head_hash,
            sequence=bytes_to_int(tail.value),
        )
        obj._expr = expr
        return obj
