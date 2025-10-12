import unittest

from src.astreum._node import Node
from src.astreum._consensus.block import Block
from src.astreum._storage.atom import ZERO32


class TestBlockAtom(unittest.TestCase):
    def setUp(self):
        # Minimal node with in-memory storage
        self.node = Node(config={})

    def test_block_to_from_atom_roundtrip(self):
        # Create a block with required fields
        b = Block()
        b.previous_block = ZERO32
        b.number = 1
        b.timestamp = 1234567890
        b.accounts_hash = b"a" * 32
        b.transactions_total_fees = 0
        b.transactions_root_hash = b"t" * 32
        b.delay_difficulty = 1
        b.delay_output = b"out"
        b.validator_public_key = b"v" * 32
        b.signature = b"sig"

        # Serialize to atoms and persist in node storage
        block_id, atoms = b.to_atom()
        for a in atoms:
            self.node._local_set(a.object_id(), a)

        # Retrieve from storage and validate fields
        b2 = Block.from_atom(self.node._local_get, block_id)
        self.assertEqual(b2.hash, block_id)
        self.assertEqual(b2.previous_block, ZERO32)
        self.assertEqual(b2.number, 1)
        self.assertEqual(b2.timestamp, 1234567890)
        self.assertEqual(b2.accounts_hash, b"a" * 32)
        self.assertEqual(b2.transactions_total_fees, 0)
        self.assertEqual(b2.transactions_root_hash, b"t" * 32)
        self.assertEqual(b2.delay_difficulty, 1)
        self.assertEqual(b2.delay_output, b"out")
        self.assertEqual(b2.validator_public_key, b"v" * 32)
        self.assertEqual(b2.signature, b"sig")
        # Body hash present
        self.assertIsInstance(b2.body_hash, (bytes, bytearray))
        self.assertTrue(b2.body_hash)


if __name__ == "__main__":
    unittest.main(verbosity=2)
