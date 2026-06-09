from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from ...machine.models.expression import Expr, resolve_list_exprs
from ...machine.models.expression import ZERO32

STATUS_SUCCESS = 0
STATUS_FAILED = 1


def _int_to_be_bytes(value: Optional[int]) -> bytes:
    if value is None:
        return b""
    value = int(value)
    if value == 0:
        return b"\x00"
    size = (value.bit_length() + 7) // 8
    return value.to_bytes(size, "big")


def _be_bytes_to_int(data: Optional[bytes]) -> int:
    if not data:
        return 0
    return int.from_bytes(data, "big")


class Receipt:
    def __init__(
        self,
        transaction_hash: bytes,
        transaction_fee: int,
        storage_fee: int,
        data_fee: int,
        execution_fee: int,
        status: int,
        logs_hash: bytes = ZERO32,
        version: int = 1,
    ) -> None:
        self.version = int(version)
        self.transaction_hash = bytes(transaction_hash)
        self.transaction_fee = int(transaction_fee)
        self.storage_fee = int(storage_fee)
        self.data_fee = int(data_fee)
        self.execution_fee = int(execution_fee)
        self.logs_hash = bytes(logs_hash)
        self.status = int(status)
        self.atom_hash = ZERO32
        self._expr: Optional["Expr"] = None

    @property
    def total_fee(self) -> int:
        return int(self.transaction_fee) + int(self.data_fee) + int(self.execution_fee) + int(self.storage_fee)

    def to_expr(self) -> "Expr":
        # Body Link chain from innermost to outermost (alphabetical field order).
        # resolve_list_exprs flattens to data_fee..transaction_hash.
        body: Expr = Expr.Link(head_hash=self.transaction_hash)
        body = Expr.Link(Expr.Bytes(_int_to_be_bytes(self.transaction_fee)), body)
        body = Expr.Link(Expr.Bytes(_int_to_be_bytes(self.storage_fee)), body)
        body = Expr.Link(Expr.Bytes(_int_to_be_bytes(self.status)), body)
        body = Expr.Link(Expr.Link(head_hash=self.logs_hash), body)
        body = Expr.Link(Expr.Bytes(_int_to_be_bytes(self.execution_fee)), body)
        body = Expr.Link(Expr.Bytes(_int_to_be_bytes(self.data_fee)), body)
        return Expr.Link(
            body,
            Expr.Link(
                Expr.Bytes(_int_to_be_bytes(self.version)),
                Expr.Symbol("receipt")))

    def expr(self) -> "Expr":
        if self._expr is not None:
            return self._expr
        self._expr = self.to_expr()
        return self._expr

    @classmethod
    def from_storage(cls, node: Any, receipt_id: bytes) -> "Receipt":
        header = node.get_expr_list(receipt_id)
        if header is None:
            raise ValueError("unable to load receipt from storage")
        if not isinstance(header, Expr.Link):
            raise ValueError("receipt header must be a Link")

        header_nodes, missed = resolve_list_exprs(node, header)
        if missed:
            raise ValueError(
                f"unable to resolve receipt header (missed={[h.hex()[:8] for h in missed]})"
            )
        if len(header_nodes) != 3:
            raise ValueError(
                f"malformed receipt header length (got={len(header_nodes)}, expected=3)"
            )

        body, ver, terminal = header_nodes
        if not isinstance(terminal, Expr.Symbol) or terminal.value != "receipt":
            raise ValueError(
                f"invalid receipt header terminal (expected Symbol('receipt'), got {terminal!r})"
            )
        if not isinstance(ver, Expr.Bytes):
            raise ValueError("invalid receipt version: expected Bytes")
        version = _be_bytes_to_int(ver.value)
        if version != 1:
            raise ValueError(f"unsupported receipt version (version={version})")
        if not isinstance(body, Expr.Link):
            raise ValueError("receipt body must be a Link chain")

        body_nodes, missed = resolve_list_exprs(node, body)
        if missed:
            raise ValueError(
                f"unable to resolve receipt body (missed={[h.hex()[:8] for h in missed]})"
            )
        if len(body_nodes) != 7:
            raise ValueError(
                f"malformed receipt body length (got={len(body_nodes)}, expected=7)"
            )

        detail_values: list[bytes] = []
        for n in body_nodes:
            if isinstance(n, Expr.Bytes):
                detail_values.append(n.value)
            elif isinstance(n, Expr.Link) and n.head_hash is not None:
                detail_values.append(n.head_hash)
            else:
                raise ValueError(f"unexpected receipt body node type: {type(n).__name__}")

        (
            data_fee_bytes,
            execution_fee_bytes,
            logs_bytes,
            status_bytes,
            storage_fee_bytes,
            transaction_fee_bytes,
            tx_hash_bytes,
        ) = detail_values

        status_value = _be_bytes_to_int(status_bytes)
        if status_value not in (STATUS_SUCCESS, STATUS_FAILED):
            raise ValueError("unsupported receipt status")

        receipt = cls(
            transaction_hash=tx_hash_bytes,
            transaction_fee=_be_bytes_to_int(transaction_fee_bytes),
            storage_fee=_be_bytes_to_int(storage_fee_bytes),
            data_fee=_be_bytes_to_int(data_fee_bytes),
            execution_fee=_be_bytes_to_int(execution_fee_bytes),
            logs_hash=logs_bytes,
            status=status_value,
            version=version,
        )
        receipt._expr = header
        receipt.atom_hash = bytes(receipt_id)
        return receipt
