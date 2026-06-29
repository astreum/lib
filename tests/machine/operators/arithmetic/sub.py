import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine
from astreum.machine.models.expression import NIL, int_, float_, bytes_, str_, symbol, link


def _is_tagged(expr, tag):
    return (
        expr._tag == "link"
        and expr._head._tag == "symbol"
        and expr._head.value == tag
    )


class TestSubOperator(unittest.TestCase):
    """sub (-) operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare sub ---

    def test_sub_int(self):
        """(10 3 -) -> 7."""
        expr, _ = parse(tokenize("(10 3 -)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 7)

    def test_sub_float(self):
        """(5.5 2.0 -) -> 3.5."""
        expr, _ = parse(tokenize("(5.5 2.0 -)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "float")
        self.assertEqual(result.value, 3.5)

    def test_sub_cross_type_returns_nil(self):
        """(1 2.0 -) -> NIL (cross-type not allowed)."""
        expr, _ = parse(tokenize("(1 2.0 -)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_sub_string_int_returns_nil(self):
        """("hello" 1 -) -> NIL (type mismatch)."""
        expr, _ = parse(tokenize('("hello" 1 -)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_sub_underflow_raises(self):
        """(-) raises IndexError."""
        expr, _ = parse(tokenize("(-)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    # --- tagged sub (?) ---

    def test_sub_int_ok(self):
        """(10 3 -?) -> (ok . 7)."""
        expr, _ = parse(tokenize("(10 3 -?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._tail._tag, "int")
        self.assertEqual(result._tail.value, 7)

    def test_sub_float_ok(self):
        """(5.5 2.0 -?) -> (ok . 3.5)."""
        expr, _ = parse(tokenize("(5.5 2.0 -?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._tail._tag, "float")
        self.assertEqual(result._tail.value, 3.5)

    def test_sub_cross_type_err(self):
        """(1 2.0 -?) -> (err . "subtraction of int and float")."""
        expr, _ = parse(tokenize("(1 2.0 -?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "subtraction of int and float")

    def test_sub_string_int_err(self):
        """("hello" 1 -?) -> (err . "subtraction of string and int")."""
        expr, _ = parse(tokenize('("hello" 1 -?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "subtraction of string and int")

    def test_sub_underflow_err(self):
        """(-?) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("(-?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
