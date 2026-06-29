from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ....machine.models.expression import Expr, NIL, resolve_list_exprs, link, int_
from ....machine.models.expression import ZERO32



@dataclass
class StorageRecord:
    creation_block_hash: bytes = b""
    last_payment_block_hash: bytes = b""
    last_payment_height: int = 0
    last_payment_winner: bytes = b""
    new_size: int = 0
    new_count: int = 0
    _expr: Optional[Expr] = field(default=None, repr=False, compare=False)

    def to_expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        # Permanent core (innermost to outermost)
        tail: Expr = int_(self.new_size)
        tail = link(int_(self.new_count), tail)
        tail = link(Expr("link", head_hash=self.creation_block_hash), tail)
        # Transient wrapper (rewritten each payment — 3 new nodes)
        tail = link(Expr("link", head_hash=self.last_payment_winner), tail)
        tail = link(int_(self.last_payment_height), tail)
        tail = link(Expr("link", head_hash=self.last_payment_block_hash), tail)
        return tail

    def expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        self._expr = self.to_expr()
        return self._expr

    @staticmethod
    def _extract_hash(n: Expr) -> bytes:
        """Extract the stored hash from a node, whether resolved or not."""
        if n._tag == "link":
            if n._head_hash is not None:
                return n._head_hash
            if n._head is not None:
                return n._head.hash()
        return ZERO32

    @classmethod
    def from_storage(cls, node: Any, expr_id: bytes) -> StorageRecord | None:
        header = node.get_expr(expr_id)
        if header is None or not header._tag == "link":
            return None
        nodes, missed = resolve_list_exprs(node, header)
        if missed:
            return None
        if len(nodes) != 6:
            return None
        # nodes[0-2]: Link hash pointers (block_hash, winner, creation)
        if not all(n._tag == "link" for n in [nodes[0], nodes[2], nodes[3]]):
            return None
        # nodes[1]: Int (height), nodes[4-5]: Int (count, size)
        if not all(n._tag == "int" for n in [nodes[1], nodes[4], nodes[5]]):
            return None
        obj = cls(
            last_payment_block_hash=cls._extract_hash(nodes[0]),
            last_payment_height=nodes[1].value,
            last_payment_winner=cls._extract_hash(nodes[2]),
            creation_block_hash=cls._extract_hash(nodes[3]),
            new_count=nodes[4].value,
            new_size=nodes[5].value,
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
        return Expr("link",
            head_hash=self.record_hash,
            tail=int_(self.sequence),
        )

    def expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        self._expr = self.to_expr()
        return self._expr

    @classmethod
    def from_storage(cls, node: Any, expr_id: bytes) -> StorageSlot | None:
        expr = node.get_expr(expr_id)
        if not expr._tag == "link":
            return None
        if expr._head_hash is None:
            return None
        tail = expr._tail
        if not tail._tag == "int":
            return None
        obj = cls(
            record_hash=expr._head_hash,
            sequence=tail.value,
        )
        obj._expr = expr
        return obj
