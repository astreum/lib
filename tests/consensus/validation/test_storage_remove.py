"""Validation tests for the STORAGE_REMOVE (0x32) transaction code.

TODO: The ``STORAGE_REMOVE`` case in ``apply.py`` is a no-op (``pass``) with
no handler implementation. Replace these tests once the handler is written.

Planned:
  prerequisites:
    - a StorageRecord registered in burn_account.data under an atom_list_id
      (via STORAGE_CREATE or pre-seeded)
  success:
    - record removed from burn_account.data
    - storage fee refunded or burned appropriately
    - receipt.status == STATUS_SUCCESS
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


class TestStorageRemove(unittest.TestCase):
    @unittest.skip("STORAGE_REMOVE handler is not implemented (no-op in apply.py)")
    def test_storage_remove_success(self):
        pass

    @unittest.skip("STORAGE_REMOVE handler is not implemented (no-op in apply.py)")
    def test_storage_remove_no_existing_record_fails(self):
        pass


if __name__ == "__main__":
    unittest.main()
