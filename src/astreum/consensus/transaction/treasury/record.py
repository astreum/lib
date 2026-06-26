from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional

from ....machine.models.expression import Expr, resolve_list_exprs
from ....machine.models.expression import ZERO32



BORROW_REQUEST_VERSION = 1
BORROW_REQUEST_SIZE = 18
U64_SIZE = 8


class LoanType(IntEnum):
    SECURED = 0
    UNSECURED = 1


@dataclass
class TreasuryUserRecord:
    balance: int = 0
    loans_root_hash: bytes = ZERO32
    total_interest_paid: int = 0
    _expr: Optional[Expr] = field(default=None, repr=False, compare=False)

    def to_expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        detail: Expr = Expr.Int(self.total_interest_paid)
        detail = Expr.Link(Expr.Link(head_hash=self.loans_root_hash), detail)
        detail = Expr.Link(Expr.Int(self.balance), detail)
        return detail

    def expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        self._expr = self.to_expr()
        return self._expr

    @classmethod
    def from_storage(cls, node: Any, head_hash: bytes) -> TreasuryUserRecord | None:
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
        fields = []
        for n in nodes:
            if isinstance(n, Expr.Int):
                fields.append(n.value)
            elif isinstance(n, Expr.Link) and n.head_hash is not None:
                fields.append(n.head_hash)
            else:
                return None
        if len(fields) != 3:
            return None
        return cls(
            balance=fields[0],
            loans_root_hash=fields[1],
            total_interest_paid=fields[2],
        )


@dataclass(frozen=True)
class TreasuryBorrowRequest:
    loan_type: LoanType
    payment_interval_blocks: int
    payment_count: int


@dataclass
class TreasuryLoanRecord:
    creation_block_number: int
    loan_type: LoanType
    discounted_amount: int
    payment_amount: int
    payment_interval_blocks: int
    next_payment_block_number: int
    payment_count: int
    _expr: Optional[Expr] = field(default=None, repr=False, compare=False)

    def to_expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        detail: Expr = Expr.Int(self.payment_interval_blocks)
        detail = Expr.Link(Expr.Int(self.payment_amount), detail)
        detail = Expr.Link(Expr.Int(self.next_payment_block_number), detail)
        detail = Expr.Link(Expr.Int(int(self.loan_type)), detail)
        detail = Expr.Link(Expr.Int(self.payment_count), detail)
        detail = Expr.Link(Expr.Int(self.discounted_amount), detail)
        detail = Expr.Link(Expr.Int(self.creation_block_number), detail)
        return detail

    def expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        self._expr = self.to_expr()
        return self._expr

    @classmethod
    def from_storage(cls, node: Any, head_hash: bytes) -> TreasuryLoanRecord | None:
        if not head_hash or head_hash == ZERO32:
            return None
        header = node.get_expr_list(head_hash)
        if header is None or not isinstance(header, Expr.Link):
            return None
        nodes, missed = resolve_list_exprs(node, header)
        if missed:
            return None
        if len(nodes) != 7:
            return None
        fields = []
        for n in nodes:
            if isinstance(n, Expr.Int):
                fields.append(n.value)
            else:
                return None
        if len(fields) != 7:
            return None
        try:
            loan_type = LoanType(fields[3])
        except ValueError:
            return None
        return cls(
            creation_block_number=fields[0],
            loan_type=loan_type,
            discounted_amount=fields[1],
            payment_count=fields[2],
            next_payment_block_number=fields[4],
            payment_amount=fields[5],
            payment_interval_blocks=fields[6],
        )


def encode_borrow_request(request: TreasuryBorrowRequest) -> bytes:
    if request.payment_interval_blocks <= 0:
        raise ValueError("payment_interval_blocks must be positive")
    if request.payment_count <= 0:
        raise ValueError("payment_count must be positive")

    return (
        bytes([BORROW_REQUEST_VERSION, int(request.loan_type)])
        + int(request.payment_interval_blocks).to_bytes(U64_SIZE, "little", signed=False)
        + int(request.payment_count).to_bytes(U64_SIZE, "little", signed=False)
    )


def decode_borrow_request(payload: bytes) -> TreasuryBorrowRequest | None:
    payload_bytes = bytes(payload)
    if len(payload_bytes) != BORROW_REQUEST_SIZE:
        return None
    if payload_bytes[0] != BORROW_REQUEST_VERSION:
        return None

    try:
        loan_type = LoanType(payload_bytes[1])
    except ValueError:
        return None

    payment_interval_blocks = int.from_bytes(
        payload_bytes[2 : 2 + U64_SIZE],
        "little",
        signed=False,
    )
    payment_count = int.from_bytes(
        payload_bytes[2 + U64_SIZE : BORROW_REQUEST_SIZE],
        "little",
        signed=False,
    )
    if payment_interval_blocks <= 0 or payment_count <= 0:
        return None

    return TreasuryBorrowRequest(
        loan_type=loan_type,
        payment_interval_blocks=payment_interval_blocks,
        payment_count=payment_count,
    )
