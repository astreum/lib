import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


class TestEvaluatorArithmetic(unittest.TestCase):
    """Arithmetic operators."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_add(self):
        """(10 20 +) -> 30."""
        expr, _ = parse(tokenize("(10 20 +)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 30)

    def test_add_overflow(self):
        """(255 1 +) -> 256 (no masking, variable-length encoding)."""
        expr, _ = parse(tokenize("(255 1 +)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertGreater(result.value, 255)

    def test_mul(self):
        """(7 8 *) -> 56."""
        expr, _ = parse(tokenize("(7 8 *)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 56)

    def test_div(self):
        """(100 7 /) -> 14."""
        expr, _ = parse(tokenize("(100 7 /)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 14)

    def test_abs_int(self):
        """(-7 abs) -> 7."""
        expr, _ = parse(tokenize("(-7 abs)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 7)

    def test_abs_float(self):
        """(-3.5 abs) -> 3.5."""
        expr, _ = parse(tokenize("(-3.5 abs)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Float)
        self.assertEqual(result.value, 3.5)

    def test_abs_underflow_returns_nil(self):
        """(abs) -> NIL."""
        expr, _ = parse(tokenize("(abs)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
