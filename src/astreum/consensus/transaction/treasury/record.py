from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional

from ....machine.models.expression import Expr, NIL, resolve_list_exprs, link, int_
from ....machine.models.expression import ZERO32
from ....storage.get.list import get_expr_list



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
        detail: Expr = link(int_(self.total_interest_paid), NIL)
        detail = link(Expr("link", head_hash=self.loans_root_hash), detail)
        detail = link(int_(self.balance), detail)
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
        header = get_expr_list(node, head_hash)
        if header is None or not header._tag == "link":
            return None
        nodes, missed = resolve_list_exprs(node, header)
        if missed:
            return None
        if len(nodes) != 3:
            return None
        fields = []
        for n in nodes:
            if n._tag == "int":
                fields.append(n.value)
            elif n._tag == "link" and n._head_hash is not None:
                fields.append(n._head_hash)
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
        detail: Expr = link(int_(self.payment_interval_blocks), NIL)
        detail = link(int_(self.payment_amount), detail)
        detail = link(int_(self.next_payment_block_number), detail)
        detail = link(int_(int(self.loan_type)), detail)
        detail = link(int_(self.payment_count), detail)
        detail = link(int_(self.discounted_amount), detail)
        detail = link(int_(self.creation_block_number), detail)
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
        header = get_expr_list(node, head_hash)
        if header is None or not header._tag == "link":
            return None
        nodes, missed = resolve_list_exprs(node, header)
        if missed:
            return None
        if len(nodes) != 7:
            return None
        fields = []
        for n in nodes:
            if n._tag == "int":
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
        bytes([BORROW_REQUEST_VERSION, request.loan_type])
        + request.payment_interval_blocks.to_bytes(U64_SIZE, "little", signed=False)
        + request.payment_count.to_bytes(U64_SIZE, "little", signed=False)
    )


def decode_borrow_request(payload: bytes) -> TreasuryBorrowRequest | None:
    payload_bytes = payload
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
