import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


class TestEvaluatorSymbol(unittest.TestCase):
    """symbol — Bytes to Symbol at runtime."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_symbol_from_bytes(self):
        """(48 symbol) -> Symbol("0")."""
        expr, _ = parse(tokenize("(48 symbol)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Symbol)
        self.assertEqual(result.value, "0")

    def test_symbol_from_link_returns_nil(self):
        """((0 0 link) symbol) -> NIL."""
        expr, _ = parse(tokenize("(0 0 link symbol)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_symbol_invalid_utf8_returns_nil(self):
        """(255 symbol) -> NIL (invalid UTF-8)."""
        expr, _ = parse(tokenize("(255 symbol)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_symbol_with_def(self):
        """(2 5 mul 120 symbol def (' x) eval) -> 10 (dynamic def)."""
        expr, _ = parse(tokenize("(2 5 mul 120 symbol def (' x) eval)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
