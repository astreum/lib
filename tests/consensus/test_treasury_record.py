import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.consensus.transaction.treasury.record import (
    TreasuryUserRecord,
)
from astreum.machine.models.expression import Expr, resolve_list_exprs


class _FakeNode:
    def get_expr(self, head_hash: bytes) -> Expr | None:
        return None


class TestTreasuryRecord(unittest.TestCase):
    def test_to_expr_uses_expected_field_order(self):
        loans_root_hash = b"\x01" * 32
        record = TreasuryUserRecord(
            balance=7,
            loans_root_hash=loans_root_hash,
            total_interest_paid=3,
        )

        expr = record.expr()
        self.assertIsNotNone(expr.hash())

        nodes, missed = resolve_list_exprs(_FakeNode(), expr)
        self.assertFalse(missed)
        self.assertEqual(len(nodes), 3)

        self.assertIsInstance(nodes[0], Expr.Int)
        self.assertEqual(nodes[0].value, 7)  # balance

        self.assertIsInstance(nodes[1], Expr.Link)
        self.assertEqual(nodes[1].head_hash, loans_root_hash)  # loans_root_hash ref

        self.assertIsInstance(nodes[2], Expr.Int)
        self.assertEqual(nodes[2].value, 3)  # total_interest_paid


if __name__ == "__main__":
    unittest.main()
