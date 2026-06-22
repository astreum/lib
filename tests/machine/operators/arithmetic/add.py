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


class TestAddOperator(unittest.TestCase):
    """add (+) operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare add ---

    def test_add_int(self):
        """(3 5 +) -> 8."""
        expr, _ = parse(tokenize("(3 5 +)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 8)

    def test_add_float(self):
        """(1.5 2.5 +) -> 4.0."""
        expr, _ = parse(tokenize("(1.5 2.5 +)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Float)
        self.assertEqual(result.value, 4.0)

    def test_add_cross_type_returns_nil(self):
        """(1 2.0 +) -> NIL (cross-type not allowed)."""
        expr, _ = parse(tokenize("(1 2.0 +)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_add_string_int_returns_nil(self):
        """("hello" 1 +) -> NIL (type mismatch)."""
        expr, _ = parse(tokenize('("hello" 1 +)'))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_add_underflow_raises(self):
        """(+) raises IndexError."""
        expr, _ = parse(tokenize("(+)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    # --- tagged add (?) ---

    def test_add_int_ok(self):
        """(3 5 +?) -> (ok . 8)."""
        expr, _ = parse(tokenize("(3 5 +?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Int)
        self.assertEqual(result.tail.value, 8)

    def test_add_float_ok(self):
        """(1.5 2.5 +?) -> (ok . 4.0)."""
        expr, _ = parse(tokenize("(1.5 2.5 +?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Float)
        self.assertEqual(result.tail.value, 4.0)

    def test_add_cross_type_err(self):
        """(1 2.0 +?) -> (err . "addition of int and float")."""
        expr, _ = parse(tokenize("(1 2.0 +?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "addition of int and float")

    def test_add_string_int_err(self):
        """("hello" 1 +?) -> (err . "addition of string and int")."""
        expr, _ = parse(tokenize('("hello" 1 +?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "addition of string and int")

    def test_add_underflow_err(self):
        """(+?) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("(+?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
