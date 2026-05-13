from __future__ import annotations

from typing import Any

from ....storage.models.atom import Atom, ZERO32
from ....storage.models.trie import Trie
from ....validation.constants import TREASURY_ADDRESS
from ....validation.models.receipt import STATUS_FAILED, STATUS_SUCCESS
from ..model import Transaction
from .discount import block_rate_fraction, calculate_discounted_amount
from .record import (
    LoanType,
    TreasuryLoanRecord,
    TreasuryUserRecord,
    decode_borrow_request,
    decode_treasury_loan_record,
    decode_treasury_user_record,
    encode_treasury_loan_record,
    encode_treasury_user_record,
)
from .utils import _remaining_payment_count, _trie_atoms


def _extend_pending_atoms(block: object, atoms: list[Atom]) -> None:
    block.pending_atoms.extend(atoms)


def secured_loan_remaining_total(
    *,
    node: Any,
    loans_root_hash: bytes,
) -> int | None:
    if not loans_root_hash or loans_root_hash == ZERO32:
        return 0

    loans_trie = Trie(root_hash=bytes(loans_root_hash))
    remaining_total = 0
    for loan_record_head in loans_trie.get_all(node).values():
        loan = decode_treasury_loan_record(node, loan_record_head)
        if loan is None:
            return None
        if loan.loan_type != LoanType.SECURED or loan.next_payment_block_number == 0:
            continue
        remaining_payment_count = _remaining_payment_count(loan)
        if remaining_payment_count is None:
            return None
        remaining_total += remaining_payment_count * loan.payment_amount
    return remaining_total


def handle_treasury_borrow(
    *,
    node: Any,
    block: object,
    transaction: Transaction,
    transaction_hash: bytes,
    sender_account: Any,
    treasury_account: Any,
) -> int:
    if (
        transaction.recipient != TREASURY_ADDRESS
        or transaction.sender == TREASURY_ADDRESS
        or transaction.amount <= 0
        or treasury_account is None
    ):
        return STATUS_FAILED

    request = decode_borrow_request(transaction.data)
    rate_fraction = block_rate_fraction(block)
    if (
        request is None
        or request.loan_type != LoanType.SECURED
        or rate_fraction is None
    ):
        return STATUS_FAILED

    rate_numerator, rate_denominator = rate_fraction
    discounted_amount = calculate_discounted_amount(
        payment_amount=transaction.amount,
        payment_interval_blocks=request.payment_interval_blocks,
        payment_count=request.payment_count,
        rate_numerator=rate_numerator,
        rate_denominator=rate_denominator,
    )
    scheduled_total = transaction.amount * request.payment_count
    user_record_head = treasury_account.data.get(node, transaction.sender)
    user_record = decode_treasury_user_record(node, user_record_head or ZERO32)
    existing_secured_total = (
        None
        if user_record is None
        else secured_loan_remaining_total(
            node=node,
            loans_root_hash=user_record.loans_root_hash or ZERO32,
        )
    )
    if (
        discounted_amount is None
        or discounted_amount <= 0
        or user_record is None
        or existing_secured_total is None
        or user_record.stake_balance - existing_secured_total < scheduled_total
        or treasury_account.balance < discounted_amount
    ):
        return STATUS_FAILED

    creation_block_number = int(
        getattr(
            block,
            "height",
            int(getattr(block.previous_block, "height", -1)) + 1,
        )
    )
    next_payment_block_number = creation_block_number + request.payment_interval_blocks
    final_payment_block_number = (
        creation_block_number + request.payment_interval_blocks * request.payment_count
    )
    loan_record_head, loan_record_atoms = encode_treasury_loan_record(
        TreasuryLoanRecord(
            creation_block_number=creation_block_number,
            loan_type=request.loan_type,
            discounted_amount=discounted_amount,
            payment_amount=transaction.amount,
            payment_interval_blocks=request.payment_interval_blocks,
            next_payment_block_number=next_payment_block_number,
            final_payment_block_number=final_payment_block_number,
        )
    )
    loans_root_hash = user_record.loans_root_hash or ZERO32
    loans_trie = Trie(
        root_hash=None if loans_root_hash == ZERO32 else bytes(loans_root_hash)
    )
    if loans_trie.get(node, transaction_hash) is not None:
        return STATUS_FAILED

    loans_trie.put(node, transaction_hash, loan_record_head)
    updated_user_record_head, updated_user_record_atoms = encode_treasury_user_record(
        TreasuryUserRecord(
            stake_balance=user_record.stake_balance,
            loans_root_hash=loans_trie.root_hash or ZERO32,
            total_interest_paid=user_record.total_interest_paid,
        )
    )
    treasury_account.data.put(
        node,
        transaction.sender,
        updated_user_record_head,
    )
    treasury_account.data_hash = treasury_account.data.root_hash or ZERO32
    treasury_account.balance -= discounted_amount
    sender_account.balance += discounted_amount
    _extend_pending_atoms(
        block,
        loan_record_atoms + _trie_atoms(loans_trie) + updated_user_record_atoms,
    )
    return STATUS_SUCCESS
