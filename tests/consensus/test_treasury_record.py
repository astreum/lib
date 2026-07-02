import sys
import unittest
import threading
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
    def __init__(self):
        self.hot_storage = {}
        self.hot_storage_lock = threading.Lock()
        self.config = {"expr_fetch_interval": 0, "expr_fetch_retries": 0}
        self.logger = type(
            "L", (), {"debug": lambda *a, **kw: None, "info": lambda *a, **kw: None}
        )()

    def get_expr(self, head_hash: bytes):
        return self.hot_storage.get(head_hash)


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

        self.assertEqual(nodes[0]._tag, "int")
        self.assertEqual(nodes[0].value, 7)  # balance

        self.assertEqual(nodes[1]._tag, "link")
        self.assertEqual(nodes[1]._head_hash, loans_root_hash)  # loans_root_hash ref

        self.assertEqual(nodes[2]._tag, "int")
        self.assertEqual(nodes[2].value, 3)  # total_interest_paid


if __name__ == "__main__":
    unittest.main()
