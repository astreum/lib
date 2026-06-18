import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


class TestEvaluatorComparison(unittest.TestCase):
    """Numeric comparison operators."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_less_than(self):
        """(1 2 <) -> 1."""
        expr, _ = parse(tokenize("(1 2 <)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x01")

    def test_greater_than(self):
        """(2 1 >) -> 1."""
        expr, _ = parse(tokenize("(2 1 >)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x01")

    def test_less_than_or_equal(self):
        """(2 2 <=) -> 1."""
        expr, _ = parse(tokenize("(2 2 <=)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x01")

    def test_greater_than_or_equal(self):
        """(2 2 >=) -> 1."""
        expr, _ = parse(tokenize("(2 2 >=)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x01")

    def test_less_than_floats(self):
        """(1.5 2.0 <) -> 1."""
        expr, _ = parse(tokenize("(1.5 2.0 <)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x01")

    def test_greater_than_floats(self):
        """(2.0 1.5 >) -> 1."""
        expr, _ = parse(tokenize("(2.0 1.5 >)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x01")

    def test_less_than_or_equal_floats(self):
        """(2.0 2.0 <=) -> 1."""
        expr, _ = parse(tokenize("(2.0 2.0 <=)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x01")

    def test_greater_than_or_equal_floats(self):
        """(2.0 2.0 >=) -> 1."""
        expr, _ = parse(tokenize("(2.0 2.0 >=)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x01")

    def test_comparison_type_mismatch_returns_nil(self):
        """(1 2.0 <) -> NIL."""
        expr, _ = parse(tokenize("(1 2.0 <)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
