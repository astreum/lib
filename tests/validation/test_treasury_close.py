"""Validation tests for the TREASURY_CLOSE (0x23) transaction code.

TODO: The handler in ``treasury/close.py`` is a stub that always returns
STATUS_SUCCESS with no state change. Replace these tests once implemented.

Planned:
  prerequisites:
    - sender has an existing TreasuryUserRecord with loans
    - all loans are fully paid (next_payment_block_number == 0)
  success:
    - user record removed or marked closed
    - remaining stake balance returned to sender
    - receipt.status == STATUS_SUCCESS
  failures:
    - outstanding loans not fully paid → STATUS_FAILED
    - no existing user record → STATUS_FAILED
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


class TestTreasuryClose(unittest.TestCase):
    @unittest.skip("treasury/close.py is a stub (always returns SUCCESS, no state change)")
    def test_treasury_close_success(self):
        pass

    @unittest.skip("treasury/close.py is a stub (always returns SUCCESS, no state change)")
    def test_treasury_close_with_outstanding_loans_fails(self):
        pass

    @unittest.skip("treasury/close.py is a stub (always returns SUCCESS, no state change)")
    def test_treasury_close_no_user_record_fails(self):
        pass


if __name__ == "__main__":
    unittest.main()
