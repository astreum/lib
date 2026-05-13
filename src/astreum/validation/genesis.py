from __future__ import annotations

from typing import Any

from .constants import BURN_ADDRESS, TREASURY_ADDRESS
from ..consensus.account import create_account
from ..consensus.transaction.treasury.record import (
    TreasuryUserRecord,
    encode_treasury_user_record,
)
from .models.accounts import Accounts
from .models.block import Block
from ..storage.models.atom import ZERO32
from ..storage.models.trie import Trie
from time import time

def create_genesis_block(
    node: Any,
    validator_public_key: bytes,
    chain_id: int = 0,
) -> Block:
    validator_pk = bytes(validator_public_key)

    if len(validator_pk) != 32:
        raise ValueError("validator_public_key must be 32 bytes")

    stake_trie = Trie()
    treasury_record_head, treasury_record_atoms = encode_treasury_user_record(
        TreasuryUserRecord(stake_balance=1)
    )
    stake_trie.put(storage_node=node, key=validator_pk, value=treasury_record_head)
    stake_root = stake_trie.root_hash or ZERO32

    treasury_account = create_account(balance=1, data_hash=stake_root, counter=0)
    treasury_account.data = stake_trie
    treasury_account.data_hash = stake_root
    burn_account = create_account(balance=0, data_hash=b"", counter=0)
    validator_account = create_account(balance=0, data_hash=b"", counter=0)

    accounts = Accounts()
    accounts.pending_atoms.extend(treasury_record_atoms)
    accounts.set_account(TREASURY_ADDRESS, treasury_account)
    accounts.set_account(BURN_ADDRESS, burn_account)
    accounts.set_account(validator_pk, validator_account)

    accounts.update_trie(node)
    accounts_root = accounts.root_hash
    if accounts_root is None:
        raise ValueError("genesis accounts trie is empty")

    block = Block(
        chain_id=chain_id,
        previous_block_hash=ZERO32,
        previous_block=None,
        height=0,
        timestamp=int(time()),
        accounts_hash=accounts_root,
        total_transaction_fee=0,
        total_storage_fee=0,
        cumulative_transaction_fee=1,
        cumulative_storage_fee=0,
        cumulative_stake=1,
        cumulative_burn=burn_account.balance,
        cumulative_mint=0,
        transactions_hash=ZERO32,
        receipts_hash=ZERO32,
        difficulty=0,
        validator_public_key_bytes=validator_pk,
        nonce=0,
        signature=b"",
        accounts=accounts,
        transactions=[],
        receipts=[],
    )

    return block
