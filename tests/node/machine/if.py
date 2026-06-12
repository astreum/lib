import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


class TestEvaluatorIf(unittest.TestCase):
    """if — conditional evaluation."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_if_truthy_takes_first_branch(self):
        """(1 (quote 42) (quote 0) if) -> 42 (truthy picks else/first)."""
        expr, _ = parse(tokenize("(1 (quote 42) (quote 0) if)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 42)

    def test_if_falsy_takes_second_branch(self):
        """(0 (quote 42) (quote 99) if) -> 99 (falsy picks then/second)."""
        expr, _ = parse(tokenize("(0 (quote 42) (quote 99) if)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 99)

    def test_if_with_computation(self):
        """(1 (2 3 +) (quote 0) if) -> 5 (evaluates the branch)."""
        expr, _ = parse(tokenize("(1 (2 3 +) (quote 0) if)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(int.from_bytes(result.value, "little"), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
