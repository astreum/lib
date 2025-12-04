
from __future__ import annotations

from typing import Any, List

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .models.account import Account
from .models.block import Block
from ..storage.models.atom import ZERO32
from ..storage.models.trie import Trie
from ..utils.integer import int_to_bytes

TREASURY_ADDRESS = b"\x01" * 32
BURN_ADDRESS = b"\x00" * 32
def create_genesis_block(node: Any, validator_public_key: bytes, validator_secret_key: bytes, chain_id: int = 0) -> Block:
    validator_pk = bytes(validator_public_key)

    if len(validator_pk) != 32:
        raise ValueError("validator_public_key must be 32 bytes")

    # 1. Stake trie with single validator stake of 1 (encoded on 32 bytes).
    stake_trie = Trie()
    stake_amount = int_to_bytes(1)
    stake_trie.put(storage_node=node, key=validator_pk, value=stake_amount)
    stake_root = stake_trie.root_hash

    # 2. Account trie with treasury, burn, and validator accounts.
    accounts_trie = Trie()

    treasury_account = Account.create(balance=1, data_hash=stake_root, counter=0)
    accounts_trie.put(storage_node=node, key=TREASURY_ADDRESS, value=treasury_account.atom_hash)

    burn_account = Account.create(balance=0, data_hash=b"", counter=0)
    accounts_trie.put(storage_node=node, key=BURN_ADDRESS, value=burn_account.atom_hash)

    validator_account = Account.create(balance=0, data_hash=b"", counter=0)
    accounts_trie.put(storage_node=node, key=validator_pk, value=validator_account.atom_hash)

    accounts_root = accounts_trie.root_hash
    if accounts_root is None:
        raise ValueError("genesis accounts trie is empty")

    # 3. Assemble block metadata.
    block = Block(
        chain_id=chain_id,
        previous_block_hash=ZERO32,
        previous_block=None,
        number=0,
        timestamp=0,
        accounts_hash=accounts_root,
        transactions_total_fees=0,
        transactions_hash=ZERO32,
        receipts_hash=ZERO32,
        delay_difficulty=0,
        delay_output=b"",
        validator_public_key=validator_pk,
        signature=b"",
        accounts=accounts_trie,
        transactions=[],
        receipts=[],
    )

    # 4. Sign the block body with the validator secret key.
    block.to_atom()
    if block.body_hash is None:
        raise ValueError("failed to materialise genesis block body")

    secret = Ed25519PrivateKey.from_private_bytes(validator_secret_key)
    block.signature = secret.sign(block.body_hash)
    block_hash, _ = block.to_atom()

    block.atom_hash = block_hash
    return block
