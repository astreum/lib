from __future__ import annotations

from typing import Any

from ....machine.models.expression import resolve_inner_exprs
from ....machine.models.expression import ZERO32
from ....storage.models.trie import Trie
from ....validation.constants import TREASURY_ADDRESS
from ....validation.models.receipt import STATUS_FAILED, STATUS_SUCCESS
from ..model import Transaction
from .record import (
    TreasuryLoanRecord,
    TreasuryUserRecord,
)
from .utils import (
    _paid_payment_count,
    _total_payment_count,
    _trie_exprs,
)


LOAN_TRANSACTION_ID_SIZE = 32


def handle_treasury_close(
    *,
    node: Any,
    block: object,
    transaction: Transaction,
) -> int:
    if (
        transaction.recipient != TREASURY_ADDRESS
        or transaction.sender == TREASURY_ADDRESS
        or transaction.amount <= 0
    ):
        return STATUS_FAILED

    treasury_account = block.accounts.get_account(address=TREASURY_ADDRESS, node=node)
    if treasury_account is None:
        return STATUS_FAILED

    loan_transaction_id = bytes(transaction.data)
    if len(loan_transaction_id) != LOAN_TRANSACTION_ID_SIZE:
        return STATUS_FAILED

    user_record_head = treasury_account.data.get(node, transaction.sender)
    user_record = TreasuryUserRecord.from_storage(node, user_record_head or ZERO32)
    if user_record is None or user_record.loans_root_hash == ZERO32:
        return STATUS_FAILED

    loans_trie = Trie(root_hash=bytes(user_record.loans_root_hash))
    loan_record_head = loans_trie.get(node, loan_transaction_id)
    loan = TreasuryLoanRecord.from_storage(node, loan_record_head or ZERO32)
    if loan is None or loan.next_payment_block_number == 0:
        return STATUS_FAILED

    total_payment_count = _total_payment_count(loan)
    if total_payment_count is None:
        return STATUS_FAILED

    current_block_number = int(
        getattr(
            block,
            "height",
            int(getattr(block.previous_block, "height", -1)) + 1,
        )
    )

    catchup_amount = 0
    next_payment = loan.next_payment_block_number

    while next_payment > 0 and next_payment <= current_block_number:
        catchup_amount += loan.payment_amount
        next_payment += loan.payment_interval_blocks
        if next_payment > loan.final_payment_block_number:
            next_payment = 0
            break

    remaining_principal = 0

    if next_payment > 0:
        if loan.payment_interval_blocks <= 0:
            return STATUS_FAILED
        paid_after = (
            (next_payment - loan.creation_block_number)
            // loan.payment_interval_blocks
        ) - 1
        remaining_count = total_payment_count - paid_after
        if remaining_count <= 0:
            return STATUS_FAILED
        remaining_principal = loan.discounted_amount * remaining_count // total_payment_count

    total_cost = catchup_amount + remaining_principal
    if total_cost <= 0 or transaction.amount < total_cost:
        return STATUS_FAILED

    updated_loan = TreasuryLoanRecord(
        creation_block_number=loan.creation_block_number,
        loan_type=loan.loan_type,
        discounted_amount=loan.discounted_amount,
        payment_amount=loan.payment_amount,
        payment_interval_blocks=loan.payment_interval_blocks,
        next_payment_block_number=0,
        final_payment_block_number=loan.final_payment_block_number,
    )
    updated_loan_head = updated_loan.expr().hash()
    loans_trie.put(node, loan_transaction_id, updated_loan_head)
    loan_exprs, _ = resolve_inner_exprs(node, updated_loan.expr())

    user_record = TreasuryUserRecord(
        balance=user_record.balance + (transaction.amount - total_cost),
        loans_root_hash=loans_trie.root_hash or ZERO32,
        total_interest_paid=user_record.total_interest_paid,
    )
    updated_user_record_head = user_record.expr().hash()
    treasury_account.data.put(node, transaction.sender, updated_user_record_head)
    treasury_account.data_hash = treasury_account.data.root_hash or ZERO32

    treasury_account.balance += transaction.amount

    user_record_exprs, _ = resolve_inner_exprs(node, user_record.expr())
    block.pending_exprs.extend(
        loan_exprs + _trie_exprs(loans_trie) + user_record_exprs
    )
    block.accounts.set_account(TREASURY_ADDRESS, treasury_account)
    return STATUS_SUCCESS
