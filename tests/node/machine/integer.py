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
    """+, *, and / operators."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_add(self):
        """(10 20 +) -> 30."""
        expr, _ = parse(tokenize("(10 20 +)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(int.from_bytes(result.value, "little"), 30)

    def test_add_overflow(self):
        """(255 1 +) -> 256 (no masking, variable-length encoding)."""
        expr, _ = parse(tokenize("(255 1 +)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertGreater(int.from_bytes(result.value, "little"), 255)

    def test_mul(self):
        """(7 8 *) -> 56."""
        expr, _ = parse(tokenize("(7 8 *)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 56)

    def test_div(self):
        """(100 7 /) -> 14."""
        expr, _ = parse(tokenize("(100 7 /)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 14)


if __name__ == "__main__":
    unittest.main(verbosity=2)
