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
from astreum.validation.validator import current_validator
from astreum.machine.models.expression import resolve_inner_exprs
from astreum.storage.actions.set import _hot_storage_set
from astreum.node import Node


class TestNodeValidator(unittest.TestCase):
    def test_current_validator_after_genesis(self) -> None:
        node = Node()
        private_key = Ed25519PrivateKey.generate()
        validator_public_key = private_key.public_key().public_bytes(
            Encoding.Raw,
            PublicFormat.Raw,
        )
        block = create_genesis_block(node, validator_public_key)
        self.assertIsNotNone(block.accounts, "genesis block must expose the accounts trie")

        account_exprs = block.accounts.update_trie(node)

        block.generate_nonce(difficulty=1)
        block_hash = block.expr().hash()
        block_exprs, _ = resolve_inner_exprs(node, block.expr())

        for e in account_exprs:
            _hot_storage_set(node, e)
        for e in block_exprs:
            _hot_storage_set(node, e)

        validator_key, _ = current_validator(
            node=node,
            block_hash=block_hash,
            target_time=block.timestamp + 1,
        )

        self.assertEqual(validator_key, validator_public_key)


if __name__ == "__main__":
    unittest.main()
