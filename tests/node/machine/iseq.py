import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


class TestEvaluatorIsEq(unittest.TestCase):
    """is_eq — structural equality."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_is_eq_equal(self):
        """(42 42 is_eq) -> 1."""
        expr, _ = parse(tokenize("(42 42 is_eq)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(int.from_bytes(result.value, "little"), 1)

    def test_is_eq_not_equal(self):
        """(42 99 is_eq) -> 0."""
        expr, _ = parse(tokenize("(42 99 is_eq)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(int.from_bytes(result.value, "little"), 0)

    def test_is_eq_combined_with_if(self):
        """((42 42 is_eq) (' (' yes)) (' (' no)) if) -> Symbol(yes)."""
        expr, _ = parse(tokenize("((42 42 is_eq) (' (' yes)) (' (' no)) if)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Symbol)
        self.assertEqual(result.value, "yes")


if __name__ == "__main__":
    unittest.main(verbosity=2)
