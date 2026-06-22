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


class TestAbsOperator(unittest.TestCase):
    """abs operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare abs ---

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

    def test_abs_string_returns_nil(self):
        """("hello" abs) -> NIL (bare dispatch catches OpError)."""
        expr, _ = parse(tokenize('("hello" abs)'))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_abs_bytes_returns_nil(self):
        """(0xdead abs) -> NIL (bare dispatch catches OpError)."""
        expr, _ = parse(tokenize("(0xdead abs)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_abs_underflow_raises(self):
        """(abs) raises IndexError."""
        expr, _ = parse(tokenize("(abs)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    # --- tagged abs (?) ---

    def test_abs_int_ok(self):
        """(-7 abs?) -> (ok . 7)."""
        expr, _ = parse(tokenize("(-7 abs?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Int)
        self.assertEqual(result.tail.value, 7)

    def test_abs_float_ok(self):
        """(-3.5 abs?) -> (ok . 3.5)."""
        expr, _ = parse(tokenize("(-3.5 abs?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Float)
        self.assertEqual(result.tail.value, 3.5)

    def test_abs_string_err(self):
        """("hello" abs?) -> (err . "absolute value of string")."""
        expr, _ = parse(tokenize('("hello" abs?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "absolute value of string")

    def test_abs_bytes_err(self):
        """(0xdead abs?) -> (err . "absolute value of bytes")."""
        expr, _ = parse(tokenize("(0xdead abs?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "absolute value of bytes")

    def test_abs_underflow_err(self):
        """(abs?) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("(abs?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
