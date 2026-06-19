"""Validation tests for the CODE_ACCOUNT_CALL (0x41) transaction code.

TODO: The handler in ``accounts/expression/call.py`` calls ``node.high_eval()``
and ``node.env_set()``, neither of which is defined on the real Node
(``env_set`` is commented out at ``node.py:74``; ``high_eval`` is absent).
The VM call path cannot be exercised without these.

Planned (once ``high_eval`` / ``env_set`` are wired):
  prerequisites:
    - CODE_ACCOUNT_CREATE first (or pre-seed an expression account at
      recipient with code_hash != ZERO32 and a stored program)
    - cost_limit > 0
    - sender balance >= tx_fee + amount + cost_limit
    - tx.data = call data
  success:
    - receipt.status == STATUS_SUCCESS
    - execution_fee == meter.used added to tx_fee
    - expression_account.balance += amount
    - any acc.pay / acc.get / acc.put effects applied
    - working accounts committed to block.accounts
  failures:
    - recipient account missing → STATUS_FAILED
    - code_hash == ZERO32 → STATUS_FAILED
    - program not in storage → STATUS_FAILED
    - cost_limit exceeded → STATUS_FAILED
    - insufficient balance for cost_limit → STATUS_FAILED
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


class TestCodeAccountCall(unittest.TestCase):
    @unittest.skip("handler calls node.high_eval()/env_set() which are not wired on Node")
    def test_call_succeeds_and_charges_execution_fee(self):
        pass

    @unittest.skip("handler calls node.high_eval()/env_set() which are not wired on Node")
    def test_call_to_nonexistent_account_fails(self):
        pass

    @unittest.skip("handler calls node.high_eval()/env_set() which are not wired on Node")
    def test_call_with_zero_code_hash_fails(self):
        pass

    @unittest.skip("handler calls node.high_eval()/env_set() which are not wired on Node")
    def test_call_program_not_in_storage_fails(self):
        pass


if __name__ == "__main__":
    unittest.main()
