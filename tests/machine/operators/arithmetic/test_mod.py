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


class TestModOperator(unittest.TestCase):
    """mod (%) operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare mod ---

    def test_mod_int(self):
        """(10 3 %) -> 1."""
        expr, _ = parse(tokenize("(10 3 %)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 1)

    def test_mod_zero_returns_nil(self):
        """(7 0 %) -> NIL (bare dispatch catches OpError)."""
        expr, _ = parse(tokenize("(7 0 %)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_mod_cross_type_returns_nil(self):
        """(1 2.0 %) -> NIL (float not allowed)."""
        expr, _ = parse(tokenize("(1 2.0 %)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_mod_string_returns_nil(self):
        """("hello" 1 %) -> NIL (string not allowed)."""
        expr, _ = parse(tokenize('("hello" 1 %)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_mod_underflow_returns_nil(self):
        """(%) -> NIL."""
        expr, _ = parse(tokenize("(%)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    # --- tagged mod (?) ---

    def test_mod_int_ok(self):
        """(10 3 %?) -> (ok . 1)."""
        expr, _ = parse(tokenize("(10 3 %?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "int")
        self.assertEqual(result._head.value, 1)

    def test_mod_zero_err(self):
        """(7 0 %?) -> (err . "modulo by zero")."""
        expr, _ = parse(tokenize("(7 0 %?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "modulo by zero")

    def test_mod_fp64_err(self):
        """(1 2.0 %?) -> (err . "modulo of int and float")."""
        expr, _ = parse(tokenize("(1 2.0 %?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "modulo of int and fp64")

    def test_mod_string_int_err(self):
        """("hello" 1 %?) -> (err . "modulo of str and int")."""
        expr, _ = parse(tokenize("(\"hello\" 1 %?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "modulo of str and int")

    def test_mod_underflow_err(self):
        """(%?) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("(%?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)