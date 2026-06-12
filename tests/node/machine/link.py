import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


class TestEvaluatorLinkOps(unittest.TestCase):
    """link, head, tail — list construction and deconstruction."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_link_constructs_pair(self):
        """(1 2 link) -> Link(1, 2)."""
        expr, _ = parse(tokenize("(1 2 link)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsInstance(result.head, Expr.Bytes)
        self.assertIsInstance(result.tail, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.head.value, "little"), 1)
        self.assertEqual(int.from_bytes(result.tail.value, "little"), 2)

    def test_head_extracts_first(self):
        """((1 2 link) head) -> 1."""
        expr, _ = parse(tokenize("((1 2 link) head)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 1)

    def test_tail_extracts_second(self):
        """((1 2 link) tail) -> 2."""
        expr, _ = parse(tokenize("((1 2 link) tail)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
