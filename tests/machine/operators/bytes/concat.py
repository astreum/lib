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


class TestConcatOperator(unittest.TestCase):
    """concat operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare concat ---

    def test_concat(self):
        """(0xdead 0xbeef concat) -> 0xde ad be ef."""
        expr, _ = parse(tokenize("(0xdead 0xbeef concat)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\xde\xad\xbe\xef")

    def test_concat_non_bytes_returns_nil(self):
        """(1 0xdead concat) -> NIL."""
        expr, _ = parse(tokenize("(1 0xdead concat)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_concat_underflow_raises(self):
        """(concat) raises IndexError."""
        expr, _ = parse(tokenize("(concat)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    # --- tagged concat (?) ---

    def test_concat_ok(self):
        """(0xdead 0xbeef concat?) -> (ok . 0xdeadbeef)."""
        expr, _ = parse(tokenize("(0xdead 0xbeef concat?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Bytes)
        self.assertEqual(result.tail.value, b"\xde\xad\xbe\xef")

    def test_concat_err(self):
        """(1 0xdead concat?) -> (err . "concatenation of int and bytes")."""
        expr, _ = parse(tokenize("(1 0xdead concat?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "concatenation of int and bytes")

    def test_concat_underflow_err(self):
        """(concat?) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("(concat?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
