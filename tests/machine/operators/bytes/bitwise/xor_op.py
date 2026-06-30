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
        and expr._tail is not None
        and expr._tail._tag == "symbol"
        and expr._tail.value == tag
    )


class TestBitwiseXorOperator(unittest.TestCase):
    """bitwise xor operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare xor ---

    def test_xor(self):
        """(0x0f 0x33 ^) -> 0x3c."""
        expr, _ = parse(tokenize("(0x0f 0x33 ^)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")

    def test_xor_non_bytes_returns_nil(self):
        """(1 0xdead ^) -> NIL."""
        expr, _ = parse(tokenize("(1 0xdead ^)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_xor_underflow_raises(self):
        """(^) raises IndexError."""
        expr, _ = parse(tokenize("(^)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    # --- tagged xor (?) ---

    def test_xor_ok(self):
        """(0x0f 0x33 ^?) -> (ok . 0x3c)."""
        expr, _ = parse(tokenize("(0x0f 0x33 ^?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "bytes")

    def test_xor_err(self):
        """(1 0xdead ^?) -> (err . "bitwise xor of int and bytes")."""
        expr, _ = parse(tokenize("(1 0xdead ^?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "bitwise xor of int and bytes")

    def test_xor_underflow_err(self):
        """(^?) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("(^?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
