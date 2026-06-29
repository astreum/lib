import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
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


class TestBitwiseOrOperator(unittest.TestCase):
    """bitwise or operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare or ---

    def test_or(self):
        """(0x0f 0x33 or) -> 0x3f."""
        expr, _ = parse(tokenize("(0x0f 0x33 or)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")

    def test_or_non_bytes_returns_nil(self):
        """(1 0xdead or) -> NIL."""
        expr, _ = parse(tokenize("(1 0xdead or)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_or_underflow_raises(self):
        """(or) raises IndexError."""
        expr, _ = parse(tokenize("(or)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    # --- tagged or (?) ---

    def test_or_ok(self):
        """(0x0f 0x33 or?) -> (ok . 0x3f)."""
        expr, _ = parse(tokenize("(0x0f 0x33 or?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._tail._tag, "bytes")

    def test_or_err(self):
        """(1 0xdead or?) -> (err . "bitwise or of int and bytes")."""
        expr, _ = parse(tokenize("(1 0xdead or?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "bitwise or of int and bytes")

    def test_or_underflow_err(self):
        """(or?) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("(or?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
