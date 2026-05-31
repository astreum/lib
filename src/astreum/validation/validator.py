from __future__ import annotations

import random
from typing import Any, Dict, Optional, Tuple

from ..machine.models.expression import resolve_inner_exprs
from .constants import TREASURY_ADDRESS
from ..consensus.account import create_account
from ..consensus.transaction.treasury.loans import (
    apply_treasury_loan_payments_from_stake_return,
)
from ..consensus.transaction.treasury.record import (
    TreasuryUserRecord,
)
from .models.accounts import Accounts
from .models.block import Block
from ..machine.models.expression import ZERO32


SLOT_DURATION_SECONDS = 2


def current_validator(
    node: Any,
    block_hash: bytes,
    target_time: Optional[int] = None,
) -> Tuple[bytes, Accounts]:
    """
    Determine the validator for the requested target_time, halving stakes once per
    slot (currently 2 seconds) between the referenced block and the target time.
    Returns the validator key and the updated accounts snapshot reflecting stake and
    balance adjustments. The RNG seed is derived from the block id.
    """

    block = Block.from_storage(node, block_hash)

    if block.timestamp is None:
        raise ValueError("block timestamp missing")

    block_timestamp = block.timestamp
    target_timestamp = int(target_time) if target_time is not None else block_timestamp + 1
    if target_timestamp <= block_timestamp:
        target_timestamp = block_timestamp + 1

    accounts_hash = getattr(block, "accounts_hash", None)
    if not accounts_hash:
        raise ValueError("block missing accounts hash")
    accounts = Accounts(root_hash=accounts_hash)

    treasury_account = accounts.get_account(TREASURY_ADDRESS, node)
    if treasury_account is None:
        raise ValueError("treasury account missing from accounts trie")

    stake_trie = treasury_account.data

    stakes: Dict[bytes, int] = {}
    stake_records: Dict[bytes, TreasuryUserRecord] = {}
    for account_key, record_head in stake_trie.get_all(node).items():
        if not account_key:
            continue
        if not record_head or record_head == ZERO32:
            continue
        stake_record = TreasuryUserRecord.from_storage(node, record_head)
        if stake_record is None:
            continue
        stakes[account_key] = stake_record.stake_balance
        stake_records[account_key] = stake_record

    if not stakes:
        raise ValueError("no validator stakes found in treasury trie")

    # Seed the validator selection RNG from the block id.
    seed_value = int.from_bytes(bytes(block_hash or getattr(block, "previous_block_hash", ZERO32)), "big", signed=False)
    rng = random.Random(seed_value)

    def pick_validator() -> bytes:
        positive_weights = [(key, weight) for key, weight in stakes.items() if weight > 0]
        if not positive_weights:
            raise ValueError("no validators with positive stake")
        total_weight = sum(weight for _, weight in positive_weights)
        choice = rng.randrange(total_weight)
        cumulative = 0
        for key, weight in sorted(positive_weights, key=lambda item: item[0]):
            cumulative += weight
            if choice < cumulative:
                return key
        return positive_weights[-1][0]

    def halve_stake(validator_key: bytes) -> None:
        current_amount = stakes.get(validator_key, 0)
        if current_amount <= 0:
            raise ValueError("validator stake must be positive")
        new_amount = current_amount // 2
        if new_amount < 1:
            new_amount = 1
        returned_amount = current_amount - new_amount
        if returned_amount <= 0:
            return

        stake_record = stake_records[validator_key]
        if stake_record.loans_root_hash == ZERO32:
            updated_stake_record = TreasuryUserRecord(
                stake_balance=new_amount,
                loans_root_hash=stake_record.loans_root_hash,
                total_interest_paid=stake_record.total_interest_paid,
            )
            updated_record_head = updated_stake_record.expr().hash()
            stake_trie.put(node, validator_key, updated_record_head)
            record_exprs, _ = resolve_inner_exprs(node, updated_stake_record.expr())
            accounts.pending_exprs.extend(record_exprs)
            treasury_account.data_hash = stake_trie.root_hash or ZERO32
            treasury_account.balance -= returned_amount

            validator_account = accounts.get_account(validator_key, node)
            if validator_account is None:
                validator_account = create_account()
            validator_account.balance += returned_amount
            accounts.set_account(validator_key, validator_account)
            stakes[validator_key] = new_amount
            stake_records[validator_key] = updated_stake_record
        else:
            if not apply_treasury_loan_payments_from_stake_return(
                node=node,
                accounts=accounts,
                borrower=validator_key,
                amount=returned_amount,
            ):
                raise ValueError("failed applying treasury loan payment from stake return")

            updated_record_head = treasury_account.data.get(node, validator_key)
            updated_stake_record = TreasuryUserRecord.from_storage(
                node,
                updated_record_head or ZERO32,
            )
            if updated_stake_record is None:
                raise ValueError("validator treasury record missing after loan payment")
            stakes[validator_key] = updated_stake_record.stake_balance
            stake_records[validator_key] = updated_stake_record

        accounts.set_account(TREASURY_ADDRESS, treasury_account)

    delta = target_timestamp - block_timestamp
    slots_to_process = max(1, (delta + SLOT_DURATION_SECONDS - 1) // SLOT_DURATION_SECONDS)

    selected_validator = pick_validator()
    halve_stake(selected_validator)
    for _ in range(1, slots_to_process):
        selected_validator = pick_validator()
        halve_stake(selected_validator)

    return selected_validator, accounts
