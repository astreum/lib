import sys
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.validation.genesis import create_genesis_block
from astreum.validation.constants import TREASURY_ADDRESS, BURN_ADDRESS
from astreum.machine.models.expression import ZERO32
from astreum.node import Node


class TestGenesisBlock(unittest.TestCase):
    def setUp(self):
        self.node = Node()
        self.private_key = Ed25519PrivateKey.generate()
        self.validator_pk = self.private_key.public_key().public_bytes(
            Encoding.Raw,
            PublicFormat.Raw,
        )

    def test_creates_block_at_height_zero(self) -> None:
        block = create_genesis_block(self.node, self.validator_pk)
        self.assertEqual(block.height, 0)
        self.assertEqual(block.previous_block_hash, ZERO32)
        self.assertEqual(block.chain_id, 0)

    def test_rejects_non_32_byte_key(self) -> None:
        with self.assertRaises(ValueError):
            create_genesis_block(self.node, b"short")
        with self.assertRaises(ValueError):
            create_genesis_block(self.node, b"x" * 33)

    def test_sets_treasury_account(self) -> None:
        block = create_genesis_block(self.node, self.validator_pk)
        self.assertIsNotNone(block.accounts)
        treasury = block.accounts.get_account(TREASURY_ADDRESS, self.node)
        self.assertIsNotNone(treasury)
        self.assertEqual(treasury.balance, 1)

    def test_sets_burn_account(self) -> None:
        block = create_genesis_block(self.node, self.validator_pk)
        self.assertIsNotNone(block.accounts)
        burn = block.accounts.get_account(BURN_ADDRESS, self.node)
        self.assertIsNotNone(burn)
        self.assertEqual(burn.balance, 0)

    def test_sets_validator_account(self) -> None:
        block = create_genesis_block(self.node, self.validator_pk)
        self.assertIsNotNone(block.accounts)
        validator = block.accounts.get_account(self.validator_pk, self.node)
        self.assertIsNotNone(validator)
        self.assertEqual(validator.balance, 0)

    def test_stake_trie_contains_validator_key(self) -> None:
        block = create_genesis_block(self.node, self.validator_pk)
        self.assertIsNotNone(block.accounts)
        treasury = block.accounts.get_account(TREASURY_ADDRESS, self.node)
        self.assertIsNotNone(treasury)
        stake_hash = treasury.data.get(self.node, self.validator_pk)
        self.assertIsNotNone(stake_hash)

    def test_accounts_trie_root_is_set(self) -> None:
        block = create_genesis_block(self.node, self.validator_pk)
        self.assertIsNotNone(block.accounts)
        self.assertIsNotNone(block.accounts_hash)
        self.assertEqual(block.accounts_hash, block.accounts.root_hash)

    def test_cumulative_fields(self) -> None:
        block = create_genesis_block(self.node, self.validator_pk)
        self.assertEqual(block.cumulative_stake, 1)
        self.assertEqual(block.cumulative_transaction_fee, 1)
        self.assertEqual(block.cumulative_storage_fee, 0)
        self.assertEqual(block.cumulative_mint, 0)
        self.assertEqual(block.cumulative_burn, 0)

    def test_empty_transactions_and_receipts(self) -> None:
        block = create_genesis_block(self.node, self.validator_pk)
        self.assertEqual(block.transactions, [])
        self.assertEqual(block.receipts, [])
        self.assertEqual(block.transactions_hash, ZERO32)
        self.assertEqual(block.receipts_hash, ZERO32)

    def test_signature_and_nonce(self) -> None:
        block = create_genesis_block(self.node, self.validator_pk)
        self.assertEqual(block.signature, b"")
        self.assertEqual(block.nonce, 0)
        self.assertEqual(block.difficulty, 0)

    def test_chain_id_passthrough(self) -> None:
        block = create_genesis_block(self.node, self.validator_pk, chain_id=42)
        self.assertEqual(block.chain_id, 42)


if __name__ == "__main__":
    unittest.main()
