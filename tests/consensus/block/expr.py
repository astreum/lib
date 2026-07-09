import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.consensus.models.block import Block  # noqa: E402
from astreum.node import Node  # noqa: E402
from astreum.expression import ZERO32, resolve_inner_exprs  # noqa: E402
from astreum.storage.put.hot import put_expr_in_hot_storage  # noqa: E402


class TestBlockExpr(unittest.TestCase):
    def setUp(self):
        # Minimal node with in-memory storage
        self.node = Node(config={})

    def test_block_to_from_expr_roundtrip(self):
        # Create a block with required fields
        b = Block(
            chain_id=0,
            previous_block_hash=ZERO32,
            previous_block=None,
            height=1,
            timestamp=1234567890,
            accounts_hash=b"a" * 32,
            total_transaction_fee=0,
            total_storage_fee=0,
            cumulative_transaction_fee=1,
            cumulative_storage_fee=0,
            cumulative_stake=1,

            cumulative_mint=0,
            transactions_hash=b"t" * 32,
            receipts_hash=b"r" * 32,
            difficulty=1,
            validator_public_key_bytes=b"v" * 32,
            signature=b"sig",
            accounts=None,
            transactions=None,
            receipts=None,
        )

        # Serialize to exprs and persist in node storage
        block_id = b.expr().hash()
        inner_exprs, _ = resolve_inner_exprs(self.node, b.expr())
        for e in inner_exprs:
            put_expr_in_hot_storage(self.node, e)

        # Retrieve from storage and validate fields
        b2 = Block.from_storage(self.node, block_id)
        self.assertEqual(b2.expr().hash(), block_id)
        self.assertEqual(b2.previous_block_hash, ZERO32)
        self.assertIsNone(b2.previous_block)
        self.assertEqual(b2.height, 1)
        self.assertEqual(b2.timestamp, 1234567890)
        self.assertEqual(b2.accounts_hash, b"a" * 32)
        self.assertEqual(b2.total_transaction_fee, 0)
        self.assertEqual(b2.total_storage_fee, 0)
        self.assertEqual(b2.total_fee, 0)
        self.assertEqual(b2.cumulative_transaction_fee, 1)
        self.assertEqual(b2.cumulative_storage_fee, 0)
        self.assertEqual(b2.cumulative_stake, 1)

        self.assertEqual(b2.cumulative_mint, 0)
        self.assertEqual(b2.transactions_hash, b"t" * 32)
        self.assertEqual(b2.receipts_hash, b"r" * 32)
        self.assertEqual(b2.difficulty, 1)
        self.assertEqual(b2.validator_public_key_bytes, b"v" * 32)
        self.assertEqual(b2.signature, b"sig")
        # Body hash present
        self.assertIsInstance(b2.body_hash, (bytes, bytearray))
        self.assertTrue(b2.body_hash)


if __name__ == "__main__":
    unittest.main(verbosity=2)
