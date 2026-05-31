from __future__ import annotations

from typing import Any

from ....machine.models.expression import Expr, resolve_inner_exprs
from ....machine.models.expression import ZERO32
from ....storage.models.trie import Trie
from ....validation.constants import TREASURY_ADDRESS
from .record import (
    LoanType,
    TreasuryLoanRecord,
    TreasuryUserRecord,
)
from .utils import (
    _interest_paid_delta,
    _paid_payment_count,
    _total_payment_count,
    _trie_exprs,
)


def _apply_treasury_loan_payment(
    *,
    node: Any,
    pending_exprs: list[Expr],
    treasury_account: Any,
    borrower: bytes,
    loans_trie: Trie,
    user_record: TreasuryUserRecord,
    loan_transaction_id: bytes,
    loan: TreasuryLoanRecord,
    amount: int,
) -> TreasuryUserRecord | None:
    if amount <= 0 or loan.payment_amount <= 0:
        return None
    if loan.next_payment_block_number == 0:
        return None
    if amount % loan.payment_amount != 0:
        return None

    total_payment_count = _total_payment_count(loan)
    paid_before = _paid_payment_count(loan)
    if total_payment_count is None or paid_before is None:
        return None
    if paid_before < 0 or paid_before >= total_payment_count:
        return None

    payment_count = amount // loan.payment_amount
    next_payment_block_number = loan.next_payment_block_number
    remaining_payments = payment_count
    while remaining_payments > 0:
        if next_payment_block_number == 0:
            return None
        if next_payment_block_number == loan.final_payment_block_number:
            next_payment_block_number = 0
            remaining_payments -= 1
            break
        next_payment_block_number += loan.payment_interval_blocks
        if next_payment_block_number > loan.final_payment_block_number:
            return None
        remaining_payments -= 1

    if remaining_payments > 0:
        return None

    if next_payment_block_number == 0:
        paid_after = total_payment_count
    else:
        paid_after = (
            (next_payment_block_number - loan.creation_block_number)
            // loan.payment_interval_blocks
        ) - 1
    if paid_after > total_payment_count:
        return None

    interest_delta = _interest_paid_delta(
        loan=loan,
        paid_before=paid_before,
        paid_after=paid_after,
        total_payment_count=total_payment_count,
    )
    if interest_delta is None:
        return None

    updated_loan = TreasuryLoanRecord(
        creation_block_number=loan.creation_block_number,
        loan_type=loan.loan_type,
        discounted_amount=loan.discounted_amount,
        payment_amount=loan.payment_amount,
        payment_interval_blocks=loan.payment_interval_blocks,
        next_payment_block_number=next_payment_block_number,
        final_payment_block_number=loan.final_payment_block_number,
    )
    updated_loan_head = updated_loan.expr().hash()
    loans_trie.put(node, loan_transaction_id, updated_loan_head)
    loan_exprs, _ = resolve_inner_exprs(node, updated_loan.expr())

    updated_user_record = TreasuryUserRecord(
        stake_balance=user_record.stake_balance,
        loans_root_hash=loans_trie.root_hash or ZERO32,
        total_interest_paid=user_record.total_interest_paid + interest_delta,
    )
    updated_user_record_head = updated_user_record.expr().hash()

    treasury_account.data.put(node, borrower, updated_user_record_head)
    treasury_account.data_hash = treasury_account.data.root_hash or ZERO32
    user_record_exprs, _ = resolve_inner_exprs(node, updated_user_record.expr())
    pending_exprs.extend(
        loan_exprs + _trie_exprs(loans_trie) + user_record_exprs
    )
    return updated_user_record


def apply_treasury_loan_payments_from_stake_return(
    *,
    node: Any,
    accounts: Any,
    borrower: bytes,
    amount: int,
) -> bool:
    """Apply stake-return value to active loans, leaving any remainder staked."""
    if amount <= 0:
        return False

    treasury_account = accounts.get_account(TREASURY_ADDRESS, node)
    if treasury_account is None:
        return False

    user_record_head = treasury_account.data.get(node, borrower)
    user_record = TreasuryUserRecord.from_storage(node, user_record_head or ZERO32)
    if user_record is None or user_record.stake_balance < amount:
        return False
    if user_record.loans_root_hash == ZERO32:
        return True

    loans_trie = Trie(root_hash=bytes(user_record.loans_root_hash))
    active_loans: list[tuple[int, bytes, TreasuryLoanRecord]] = []
    for loan_transaction_id, loan_record_head in loans_trie.get_all(node).items():
        loan = TreasuryLoanRecord.from_storage(node, loan_record_head)
        if (
            loan is None
            or loan.loan_type != LoanType.SECURED
            or loan.next_payment_block_number == 0
        ):
            continue
        active_loans.append(
            (loan.next_payment_block_number, bytes(loan_transaction_id), loan)
        )

    if not active_loans:
        return True

    available_amount = amount
    applied_amount = 0
    current_user_record = user_record
    ordered_loans = [
        (loan_transaction_id, loan)
        for _, loan_transaction_id, loan in sorted(active_loans)
    ]
    while available_amount > 0 and ordered_loans:
        applied_this_pass = False
        next_pass_loans: list[tuple[bytes, TreasuryLoanRecord]] = []
        for loan_transaction_id, loan in ordered_loans:
            if loan.payment_amount <= 0:
                continue
            if available_amount < loan.payment_amount:
                next_pass_loans.append((loan_transaction_id, loan))
                continue

            next_stake_balance = current_user_record.stake_balance - loan.payment_amount
            if next_stake_balance < 0:
                return False

            updated_user_record = _apply_treasury_loan_payment(
                node=node,
                pending_exprs=accounts.pending_exprs,
                treasury_account=treasury_account,
                borrower=borrower,
                loans_trie=loans_trie,
                user_record=TreasuryUserRecord(
                    stake_balance=next_stake_balance,
                    loans_root_hash=current_user_record.loans_root_hash,
                    total_interest_paid=current_user_record.total_interest_paid,
                ),
                loan_transaction_id=loan_transaction_id,
                loan=loan,
                amount=loan.payment_amount,
            )
            if updated_user_record is None:
                return False

            current_user_record = updated_user_record
            available_amount -= loan.payment_amount
            applied_amount += loan.payment_amount
            applied_this_pass = True

            next_payment_block_number = (
                0
                if loan.next_payment_block_number == loan.final_payment_block_number
                else loan.next_payment_block_number + loan.payment_interval_blocks
            )
            if next_payment_block_number != 0:
                next_pass_loans.append(
                    (
                        loan_transaction_id,
                        TreasuryLoanRecord(
                            creation_block_number=loan.creation_block_number,
                            loan_type=loan.loan_type,
                            discounted_amount=loan.discounted_amount,
                            payment_amount=loan.payment_amount,
                            payment_interval_blocks=loan.payment_interval_blocks,
                            next_payment_block_number=next_payment_block_number,
                            final_payment_block_number=loan.final_payment_block_number,
                        ),
                    )
                )

        if not applied_this_pass:
            break
        ordered_loans = next_pass_loans

    if applied_amount == 0:
        return True

    accounts.set_account(TREASURY_ADDRESS, treasury_account)
    return True
