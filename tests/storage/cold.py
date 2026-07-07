from __future__ import annotations

import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine.models.expression import Expr, bytes_
from astreum.node import Node
from astreum.storage.get.single.cold.get import get_expr_from_cold_storage
from astreum.storage.put.cold.insert import put_expr_in_cold_storage


class TestColdStorage(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.node = Node(
            {
                "cold_storage_path": self.temp_dir.name,
                "cold_storage_scale": "KB",
                "default_seed": None,
                "verbose": False,
            }
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @staticmethod
    def _make_expr(value: int) -> Expr:
        data = value.to_bytes(64, "big", signed=False)
        return bytes_(data)

    def test_compaction_merges_to_level_2(self) -> None:
        level_2_path = Path(self.temp_dir.name) / "level_2"
        expected: dict[bytes, bytes] = {}

        max_atoms = 64
        for value in range(1, max_atoms + 1):
            expr = self._make_expr(value)
            expr_id = expr.hash()
            expected[expr_id] = expr.value
            stored = put_expr_in_cold_storage(self.node, expr)
            self.assertTrue(stored, "failed to store expr")
            if level_2_path.exists() and any(level_2_path.glob("*_index")):
                break
        else:
            self.fail("cold storage did not merge into level_2")

        self.assertTrue(level_2_path.exists(), "level_2 directory missing")
        self.assertTrue(any(level_2_path.glob("*_data")), "level_2 data file missing")
        level_1_path = Path(self.temp_dir.name) / "level_1"
        if level_1_path.exists():
            self.assertFalse(
                any(level_1_path.glob("*_index")),
                "level_1 index files should be cleared after merge",
            )
            self.assertFalse(
                any(level_1_path.glob("*_data")),
                "level_1 data files should be cleared after merge",
            )

        rng = random.Random(1337)
        sample_size = min(5, len(expected))
        for expr_id in rng.sample(list(expected.keys()), k=sample_size):
            expr = get_expr_from_cold_storage(self.node, expr_id)
            self.assertIsNotNone(expr, "missing expr after compaction")
            self.assertEqual(expr._tag, "bytes", "expected Bytes expr")
            self.assertEqual(expr.value, expected[expr_id], "expr data mismatch")


if __name__ == "__main__":
    unittest.main()
