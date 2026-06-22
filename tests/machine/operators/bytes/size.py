import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
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


class TestSizeOperator(unittest.TestCase):
    """size operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare size ---

    def test_size(self):
        """(0xdeadbeef size) -> 4."""
        expr, _ = parse(tokenize("(0xdeadbeef size)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 4)

    def test_size_non_bytes_returns_nil(self):
        """(42 size) -> NIL (type mismatch)."""
        expr, _ = parse(tokenize("(42 size)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_size_underflow_raises(self):
        """(size) raises IndexError."""
        expr, _ = parse(tokenize("(size)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    # --- tagged size (?) ---

    def test_size_ok(self):
        """(0xdeadbeef size?) -> (ok . 4)."""
        expr, _ = parse(tokenize("(0xdeadbeef size?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Int)
        self.assertEqual(result.tail.value, 4)

    def test_size_err(self):
        """(42 size?) -> (err . "size of int")."""
        expr, _ = parse(tokenize("(42 size?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "size of int")

    def test_size_underflow_err(self):
        """(size?) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("(size?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
