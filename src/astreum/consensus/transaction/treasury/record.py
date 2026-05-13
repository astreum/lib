from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ....storage.models.atom import Atom, AtomKind, ZERO32, bytes_list_to_atoms
from ....utils.integer import bytes_to_int, int_to_bytes


BORROW_REQUEST_VERSION = 1
BORROW_REQUEST_SIZE = 18
LOAN_RECORD_FIELD_COUNT = 7
TREASURY_USER_RECORD_FIELD_COUNT = 3
U64_SIZE = 8


class LoanType(IntEnum):
    SECURED = 0
    UNSECURED = 1


@dataclass(frozen=True)
class TreasuryUserRecord:
    stake_balance: int = 0
    loans_root_hash: bytes = ZERO32
    total_interest_paid: int = 0


@dataclass(frozen=True)
class TreasuryBorrowRequest:
    loan_type: LoanType
    payment_interval_blocks: int
    payment_count: int


@dataclass(frozen=True)
class TreasuryLoanRecord:
    creation_block_number: int
    loan_type: LoanType
    discounted_amount: int
    payment_amount: int
    payment_interval_blocks: int
    next_payment_block_number: int
    final_payment_block_number: int


def encode_treasury_user_record(record: TreasuryUserRecord) -> tuple[bytes, list[Atom]]:
    loans_root_hash = bytes(record.loans_root_hash or ZERO32)
    if len(loans_root_hash) != len(ZERO32):
        raise ValueError("loans_root_hash must be 32 bytes")
    if record.stake_balance < 0:
        raise ValueError("stake_balance must be non-negative")
    if record.total_interest_paid < 0:
        raise ValueError("total_interest_paid must be non-negative")

    return bytes_list_to_atoms(
        [
            int_to_bytes(record.stake_balance),
            loans_root_hash,
            int_to_bytes(record.total_interest_paid),
        ]
    )


def decode_treasury_user_record(node: Any, record_head: bytes) -> TreasuryUserRecord | None:
    if not record_head or record_head == ZERO32:
        return None

    record_atoms = node.get_atom_list(bytes(record_head))
    if record_atoms is None or len(record_atoms) != TREASURY_USER_RECORD_FIELD_COUNT:
        return None
    if any(record_atom.kind is not AtomKind.BYTES for record_atom in record_atoms):
        return None

    loans_root_hash = bytes(record_atoms[1].data or ZERO32)
    if len(loans_root_hash) != len(ZERO32):
        return None

    return TreasuryUserRecord(
        stake_balance=bytes_to_int(record_atoms[0].data),
        loans_root_hash=loans_root_hash,
        total_interest_paid=bytes_to_int(record_atoms[2].data),
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


def encode_treasury_loan_record(record: TreasuryLoanRecord) -> tuple[bytes, list[Atom]]:
    if record.creation_block_number < 0:
        raise ValueError("creation_block_number must be non-negative")
    try:
        loan_type = LoanType(record.loan_type)
    except ValueError as exc:
        raise ValueError("invalid loan_type") from exc
    if record.discounted_amount <= 0:
        raise ValueError("discounted_amount must be positive")
    if record.payment_amount <= 0:
        raise ValueError("payment_amount must be positive")
    if record.payment_interval_blocks <= 0:
        raise ValueError("payment_interval_blocks must be positive")
    if (
        record.next_payment_block_number != 0
        and record.next_payment_block_number <= record.creation_block_number
    ):
        raise ValueError("next_payment_block_number must be after creation or 0 when closed")
    if (
        record.next_payment_block_number != 0
        and record.final_payment_block_number < record.next_payment_block_number
    ):
        raise ValueError("final_payment_block_number must be after next payment")

    return bytes_list_to_atoms(
        [
            int_to_bytes(record.creation_block_number),
            int_to_bytes(int(loan_type)),
            int_to_bytes(record.discounted_amount),
            int_to_bytes(record.payment_amount),
            int_to_bytes(record.payment_interval_blocks),
            int_to_bytes(record.next_payment_block_number),
            int_to_bytes(record.final_payment_block_number),
        ]
    )


def decode_treasury_loan_record(node: Any, record_head: bytes) -> TreasuryLoanRecord | None:
    if not record_head or record_head == ZERO32:
        return None

    record_atoms = node.get_atom_list(bytes(record_head))
    if record_atoms is None or len(record_atoms) != LOAN_RECORD_FIELD_COUNT:
        return None
    if any(record_atom.kind is not AtomKind.BYTES for record_atom in record_atoms):
        return None

    try:
        loan_type = LoanType(bytes_to_int(record_atoms[1].data))
    except ValueError:
        return None

    return TreasuryLoanRecord(
        creation_block_number=bytes_to_int(record_atoms[0].data),
        loan_type=loan_type,
        discounted_amount=bytes_to_int(record_atoms[2].data),
        payment_amount=bytes_to_int(record_atoms[3].data),
        payment_interval_blocks=bytes_to_int(record_atoms[4].data),
        next_payment_block_number=bytes_to_int(record_atoms[5].data),
        final_payment_block_number=bytes_to_int(record_atoms[6].data),
    )
