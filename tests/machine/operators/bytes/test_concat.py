import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine
from astreum.machine.models.expression import NIL, int_, fp64_, bytes_, str_, symbol, link


def _is_tagged(expr, tag):
    return (
        expr._tag == "link"
        and expr._tail is not None
        and expr._tail._tag == "symbol"
        and expr._tail.value == tag
    )


class TestConcatOperator(unittest.TestCase):
    """concat operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare concat ---

    def test_concat(self):
        """(0xdead 0xbeef concat) -> 0xde ad be ef."""
        expr, _ = parse(tokenize("(0xdead 0xbeef concat)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\xde\xad\xbe\xef")

    def test_concat_non_bytes_returns_nil(self):
        """(1 0xdead concat) -> NIL."""
        expr, _ = parse(tokenize("(1 0xdead concat)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_concat_underflow_raises(self):
        """(concat) raises IndexError."""
        expr, _ = parse(tokenize("(concat)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    # --- tagged concat (?) ---

    def test_concat_ok(self):
        """(0xdead 0xbeef 'concat try) -> (ok . 0xdeadbeef)."""
        expr, _ = parse(tokenize("(0xdead 0xbeef 'concat try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "bytes")
        self.assertEqual(result._head.value, b"\xde\xad\xbe\xef")

    def test_concat_err(self):
        """(1 0xdead 'concat try) -> (err . "concatenation of int and bytes")."""
        expr, _ = parse(tokenize("(1 0xdead 'concat try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "concatenation of int and bytes")

    def test_concat_underflow_err(self):
        """('concat try) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("('concat try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)