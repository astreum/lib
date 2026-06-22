import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine
from astreum.machine.models.expression import NIL


def _is_tagged(expr, tag):
    return (
        isinstance(expr, Expr.Link)
        and isinstance(expr.head, Expr.Symbol)
        and expr.head.value == tag
    )


class TestBitwiseAndOperator(unittest.TestCase):
    """bitwise and operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare and ---

    def test_and(self):
        """(0x0f 0x33 and) -> 0x03."""
        expr, _ = parse(tokenize("(0x0f 0x33 and)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)

    def test_and_non_bytes_returns_nil(self):
        """(1 0xdead and) -> NIL."""
        expr, _ = parse(tokenize("(1 0xdead and)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_and_underflow_raises(self):
        """(and) raises IndexError."""
        expr, _ = parse(tokenize("(and)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    # --- tagged and (?) ---

    def test_and_ok(self):
        """(0x0f 0x33 and?) -> (ok . 0x03)."""
        expr, _ = parse(tokenize("(0x0f 0x33 and?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Bytes)

    def test_and_err(self):
        """(1 0xdead and?) -> (err . "bitwise and of int and bytes")."""
        expr, _ = parse(tokenize("(1 0xdead and?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "bitwise and of int and bytes")

    def test_and_underflow_err(self):
        """(and?) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("(and?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
