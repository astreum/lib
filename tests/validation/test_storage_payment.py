"""Validation tests for the STORAGE_PAYMENT (0x31) transaction code.

TODO: The handler in ``storage/payment.py`` calls ``node.get_atom()``, which
is not wired on the real Node (only ``get_atom_list`` exists at
``node.py:89``). The challenge/PoW/payout path cannot be exercised without
an extended fake node that provides ``get_atom``.

Planned (once ``get_atom`` exists):
  prerequisites:
    - STORAGE_CREATE first to register a StorageRecord under atom_list_id
    - store atoms in node
    - derive challenge_index from blake3(last_payment_block_hash + atom_list_id)
    - brute-force a nonce so blake3(prev_block_hash + sender + list_id +
      challenge_data_hash + nonce) has >= required_bits leading zeros
    - block.height > last_payment_block.height
  success:
    - sender.balance += (new_size * height_diff)
    - block.total_mint increased
    - record.last_payment_winner == sender
    - record.last_payment_block_hash updated
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


class TestStoragePayment(unittest.TestCase):
    @unittest.skip("handler calls node.get_atom() which is not wired on Node")
    def test_storage_payment_success(self):
        pass

    @unittest.skip("handler calls node.get_atom() which is not wired on Node")
    def test_storage_payment_no_contract_fails(self):
        pass

    @unittest.skip("handler calls node.get_atom() which is not wired on Node")
    def test_storage_payment_insufficient_pow_fails(self):
        pass


if __name__ == "__main__":
    unittest.main()
