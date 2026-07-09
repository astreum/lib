import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine
from astreum.expression import NIL, int_, fp64_, bytes_, str_, symbol, link


def _is_tagged(expr, tag):
    return (
        expr._tag == "link"
        and expr._tail is not None
        and expr._tail._tag == "symbol"
        and expr._tail.value == tag
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
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 15)

    def test_mul_float(self):
        """(1.5 2.0 *) -> 3.0."""
        expr, _ = parse(tokenize("(1.5 2.0 *)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "fp64")
        self.assertEqual(result.value, 3.0)

    def test_mul_cross_type_returns_nil(self):
        """(1 2.0 *) -> NIL (cross-type not allowed)."""
        expr, _ = parse(tokenize("(1 2.0 *)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_mul_string_int_returns_nil(self):
        """("hello" 3 *) -> NIL (type mismatch)."""
        expr, _ = parse(tokenize('("hello" 3 *)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_mul_underflow_raises(self):
        """(*) raises IndexError."""
        expr, _ = parse(tokenize("(*)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    # --- tagged mul (?) ---

    def test_mul_int_ok(self):
        """(3 5 '* try) -> (ok . 15)."""
        expr, _ = parse(tokenize("(3 5 '* try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "int")
        self.assertEqual(result._head.value, 15)

    def test_mul_fp64_ok(self):
        """(1.5 2.0 '* try) -> (ok . 3.0)."""
        expr, _ = parse(tokenize("(1.5 2.0 '* try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "fp64")
        self.assertEqual(result._head.value, 3.0)

    def test_mul_cross_type_err(self):
        """(1 2.0 '* try) -> (err . "multiplication of int and float")."""
        expr, _ = parse(tokenize("(1 2.0 '* try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "multiplication of int and fp64")

    def test_mul_string_int_err(self):
        """("hello" 3 '* try) -> (err . "multiplication of str and int")."""
        expr, _ = parse(tokenize("(\"hello\" 3  '* try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "multiplication of str and int")

    def test_mul_underflow_err(self):
        """('* try) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("('* try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)