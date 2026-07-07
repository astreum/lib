from __future__ import annotations

from typing import Any

from ....machine.models.expression import resolve_inner_exprs
from ....machine.models.expression import ZERO32
from ....storage.radix import RadixTree, get_from_radix_tree, put_in_radix_tree
from ...constants import TREASURY_ADDRESS
from ...models.receipt import STATUS_FAILED, STATUS_SUCCESS
from ..model import Transaction
from .record import (
    TreasuryLoanRecord,
    TreasuryUserRecord,
)
from .utils import (
    _interest_paid_delta,
    _paid_payment_count,
    _trie_exprs,
)


LOAN_TRANSACTION_ID_SIZE = 32


def handle_treasury_repay(
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

    loan_transaction_id = transaction.data.value if transaction.data._tag == "bytes" else b""
    if len(loan_transaction_id) != LOAN_TRANSACTION_ID_SIZE:
        return STATUS_FAILED

    user_record_head = get_from_radix_tree(treasury_account.data, node, transaction.sender)
    user_record = TreasuryUserRecord.from_storage(node, user_record_head or ZERO32)
    if user_record is None or user_record.loans_root_hash == ZERO32:
        return STATUS_FAILED

    loans_trie = RadixTree(root_hash=user_record.loans_root_hash)
    loan_record_head = get_from_radix_tree(loans_trie, node, loan_transaction_id)
    loan = TreasuryLoanRecord.from_storage(node, loan_record_head or ZERO32)
    if loan is None or loan.next_payment_block_number == 0:
        return STATUS_FAILED
    if loan.payment_amount <= 0 or transaction.amount % loan.payment_amount != 0:
        return STATUS_FAILED

    total_payment_count = loan.payment_count
    paid_before = _paid_payment_count(loan)
    if total_payment_count <= 0 or paid_before is None:
        return STATUS_FAILED
    if paid_before < 0 or paid_before >= total_payment_count:
        return STATUS_FAILED

    final_payment_block_number = (
        loan.creation_block_number
        + loan.payment_interval_blocks * loan.payment_count
    )
    payment_count = transaction.amount // loan.payment_amount
    next_payment_block_number = loan.next_payment_block_number
    remaining_payments = payment_count
    while remaining_payments > 0:
        if next_payment_block_number == 0:
            return STATUS_FAILED
        if next_payment_block_number == final_payment_block_number:
            next_payment_block_number = 0
            remaining_payments -= 1
            break
        next_payment_block_number += loan.payment_interval_blocks
        if next_payment_block_number > final_payment_block_number:
            return STATUS_FAILED
        remaining_payments -= 1

    if remaining_payments > 0:
        return STATUS_FAILED

    if next_payment_block_number == 0:
        paid_after = total_payment_count
    else:
        paid_after = (
            (next_payment_block_number - loan.creation_block_number)
            // loan.payment_interval_blocks
        ) - 1
    if paid_after > total_payment_count:
        return STATUS_FAILED

    interest_delta = _interest_paid_delta(
        loan=loan,
        paid_before=paid_before,
        paid_after=paid_after,
        total_payment_count=total_payment_count,
    )
    if interest_delta is None:
        return STATUS_FAILED

    updated_loan = TreasuryLoanRecord(
        creation_block_number=loan.creation_block_number,
        loan_type=loan.loan_type,
        discounted_amount=loan.discounted_amount,
        payment_amount=loan.payment_amount,
        payment_interval_blocks=loan.payment_interval_blocks,
        next_payment_block_number=next_payment_block_number,
        payment_count=loan.payment_count,
    )
    updated_loan_head = updated_loan.expr().hash()
    put_in_radix_tree(loans_trie, node, loan_transaction_id, updated_loan_head)
    loan_exprs, _ = resolve_inner_exprs(node, updated_loan.expr())

    user_record = TreasuryUserRecord(
        balance=user_record.balance,
        loans_root_hash=loans_trie.root_hash or ZERO32,
        total_interest_paid=user_record.total_interest_paid + interest_delta,
    )
    updated_user_record_head = user_record.expr().hash()
    put_in_radix_tree(treasury_account.data, node, transaction.sender, updated_user_record_head)
    treasury_account.data_hash = treasury_account.data.root_hash or ZERO32
    treasury_account.balance += transaction.amount
    user_record_exprs, _ = resolve_inner_exprs(node, user_record.expr())
    block.pending_exprs.extend(
        loan_exprs + _trie_exprs(loans_trie) + user_record_exprs
    )
    block.accounts.set_account(TREASURY_ADDRESS, treasury_account)
    return STATUS_SUCCESS
