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


class TestSqrtOperator(unittest.TestCase):
    """sqrt operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare sqrt ---

    def test_sqrt_float(self):
        """(9.0 sqrt) -> 3.0."""
        expr, _ = parse(tokenize("(9.0 sqrt)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "float")
        self.assertEqual(result.value, 3.0)

    def test_sqrt_negative_returns_nil(self):
        """(-1.0 sqrt) -> NIL (bare dispatch catches OpError)."""
        expr, _ = parse(tokenize("(-1.0 sqrt)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_sqrt_int_returns_nil(self):
        """(42 sqrt) -> NIL (int not allowed)."""
        expr, _ = parse(tokenize("(42 sqrt)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_sqrt_string_returns_nil(self):
        """("hello" sqrt) -> NIL (string not allowed)."""
        expr, _ = parse(tokenize('("hello" sqrt)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_sqrt_underflow_raises(self):
        """(sqrt) raises IndexError."""
        expr, _ = parse(tokenize("(sqrt)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    # --- tagged sqrt (?) ---

    def test_sqrt_float_ok(self):
        """(9.0 sqrt?) -> (ok . 3.0)."""
        expr, _ = parse(tokenize("(9.0 sqrt?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._tail._tag, "float")
        self.assertEqual(result._tail.value, 3.0)

    def test_sqrt_negative_err(self):
        """(-1.0 sqrt?) -> (err . "square root of negative number")."""
        expr, _ = parse(tokenize("(-1.0 sqrt?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "square root of negative number")

    def test_sqrt_int_err(self):
        """(42 sqrt?) -> (err . "square root of int")."""
        expr, _ = parse(tokenize("(42 sqrt?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "square root of int")

    def test_sqrt_string_err(self):
        """("hello" sqrt?) -> (err . "square root of string")."""
        expr, _ = parse(tokenize('("hello" sqrt?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "square root of string")

    def test_sqrt_bytes_err(self):
        """(0xdead sqrt?) -> (err . "square root of bytes")."""
        expr, _ = parse(tokenize("(0xdead sqrt?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "square root of bytes")

    def test_sqrt_underflow_err(self):
        """(sqrt?) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("(sqrt?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
