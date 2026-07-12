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


class TestAddOperator(unittest.TestCase):
    """add (+) operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare add ---

    def test_add_int(self):
        """(3 5 +) -> 8."""
        expr, _ = parse(tokenize("(3 5 +)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result._value, 8)

    def test_add_float(self):
        """(1.5 2.5 +) -> 4.0 (as fp64, precision doubled from fp64 stays fp64)."""
        expr, _ = parse(tokenize("(1.5 2.5 +)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "fp64")
        self.assertEqual(result._value, 4.0)

    def test_add_cross_type_returns_nil(self):
        """(1 2.0 +) -> NIL (cross-type not allowed)."""
        expr, _ = parse(tokenize("(1 2.0 +)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_add_string_int_returns_nil(self):
        '''("hello" 1 +) -> NIL (type mismatch).'''
        expr, _ = parse(tokenize('("hello" 1 +)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_add_underflow_returns_nil(self):
        """(+) -> NIL."""
        expr, _ = parse(tokenize("(+)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    # --- tagged add (?) ---

    def test_add_int_ok(self):
        """(3 5 +?) -> (ok . 8)."""
        expr, _ = parse(tokenize("(3 5 +?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "int")
        self.assertEqual(result._head._value, 8)

    def test_add_fp64_ok(self):
        """(1.5 2.5 +?) -> (ok . 4.0)."""
        expr, _ = parse(tokenize("(1.5 2.5 +?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "fp64")
        self.assertEqual(result._head._value, 4.0)

    def test_add_cross_type_err(self):
        '''(1 2.0 +?) -> (err . "addition of int and fp64").'''
        expr, _ = parse(tokenize("(1 2.0 +?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "addition of int and fp64")

    def test_add_string_int_err(self):
        '''("hello" 1 +?) -> (err . "addition of str and int").'''
        expr, _ = parse(tokenize("(\"hello\" 1 +?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "addition of str and int")

    def test_add_underflow_err(self):
        """(+?) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("(+?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)