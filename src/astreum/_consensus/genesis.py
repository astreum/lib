
from __future__ import annotations

from typing import Any, List

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .account import Account
from .block import Block
from .._storage.atom import ZERO32
from .._storage.patricia import PatriciaTrie
from ..utils.integer import int_to_bytes

TREASURY_ADDRESS = b"\x01" * 32
BURN_ADDRESS = b"\x00" * 32
def create_genesis_block(node: Any, validator_public_key: bytes, validator_secret_key: bytes) -> Block:
    validator_pk = bytes(validator_public_key)

    if len(validator_pk) != 32:
        raise ValueError("validator_public_key must be 32 bytes")

    # 1. Stake trie with single validator stake of 1 (encoded on 32 bytes).
    stake_trie = PatriciaTrie()
    stake_amount = int_to_bytes(1)
    stake_trie.put(storage_node=node, key=validator_pk, value=stake_amount)
    stake_root = stake_trie.root_hash

    # 2. Account trie with treasury, burn, and validator accounts.
    accounts_trie = PatriciaTrie()

    treasury_account = Account.create(balance=1, data=stake_root, counter=0)
    accounts_trie.put(storage_node=node, key=TREASURY_ADDRESS, value=treasury_account.hash)

    burn_account = Account.create(balance=0, data=b"", counter=0)
    accounts_trie.put(storage_node=node, key=BURN_ADDRESS, value=burn_account.hash)

    validator_account = Account.create(balance=0, data=b"", counter=0)
    accounts_trie.put(storage_node=node, key=validator_pk, value=validator_account.hash)

    accounts_root = accounts_trie.root_hash
    if accounts_root is None:
        raise ValueError("genesis accounts trie is empty")

    # 3. Assemble block metadata.
    block = Block()
    block.previous_block_hash = ZERO32
    block.number = 0
    block.timestamp = 0
    block.accounts_hash = accounts_root
    block.accounts = accounts_trie
    block.transactions_total_fees = 0
    block.transactions_hash = ZERO32
    block.receipts_hash = ZERO32
    block.delay_difficulty = 0
    block.delay_output = b""
    block.validator_public_key = validator_pk
    block.transactions = []
    block.receipts = []

    # 4. Sign the block body with the validator secret key.
    block.signature = b""
    block.to_atom()

    if block.body_hash is None:
        raise ValueError("failed to materialise genesis block body")

    secret = Ed25519PrivateKey.from_private_bytes(validator_secret_key)
    block.signature = secret.sign(block.body_hash)
    block_hash, _ = block.to_atom()

    block.hash = block_hash
    return block
