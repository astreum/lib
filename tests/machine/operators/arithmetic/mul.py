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


class TestMulOperator(unittest.TestCase):
    """mul (*) operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare mul ---

    def test_mul_int(self):
        """(3 5 *) -> 15."""
        expr, _ = parse(tokenize("(3 5 *)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 15)

    def test_mul_float(self):
        """(1.5 2.0 *) -> 3.0."""
        expr, _ = parse(tokenize("(1.5 2.0 *)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Float)
        self.assertEqual(result.value, 3.0)

    def test_mul_cross_type_returns_nil(self):
        """(1 2.0 *) -> NIL (cross-type not allowed)."""
        expr, _ = parse(tokenize("(1 2.0 *)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_mul_string_int_returns_nil(self):
        """("hello" 3 *) -> NIL (type mismatch)."""
        expr, _ = parse(tokenize('("hello" 3 *)'))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_mul_underflow_raises(self):
        """(*) raises IndexError."""
        expr, _ = parse(tokenize("(*)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    # --- tagged mul (?) ---

    def test_mul_int_ok(self):
        """(3 5 *?) -> (ok . 15)."""
        expr, _ = parse(tokenize("(3 5 *?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Int)
        self.assertEqual(result.tail.value, 15)

    def test_mul_float_ok(self):
        """(1.5 2.0 *?) -> (ok . 3.0)."""
        expr, _ = parse(tokenize("(1.5 2.0 *?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Float)
        self.assertEqual(result.tail.value, 3.0)

    def test_mul_cross_type_err(self):
        """(1 2.0 *?) -> (err . "multiplication of int and float")."""
        expr, _ = parse(tokenize("(1 2.0 *?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "multiplication of int and float")

    def test_mul_string_int_err(self):
        """("hello" 3 *?) -> (err . "multiplication of string and int")."""
        expr, _ = parse(tokenize('("hello" 3 *?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "multiplication of string and int")

    def test_mul_underflow_err(self):
        """(*?) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("(*?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
