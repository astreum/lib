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


class TestSizeOperator(unittest.TestCase):
    """size operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare size ---

    def test_size(self):
        """(0xdeadbeef size) -> 4."""
        expr, _ = parse(tokenize("(0xdeadbeef size)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 4)

    def test_size_non_bytes_returns_nil(self):
        """(42 size) -> NIL (type mismatch)."""
        expr, _ = parse(tokenize("(42 size)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_size_underflow_raises(self):
        """(size) raises IndexError."""
        expr, _ = parse(tokenize("(size)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    # --- tagged size (?) ---

    def test_size_ok(self):
        """(0xdeadbeef 'size try) -> (ok . 4)."""
        expr, _ = parse(tokenize("(0xdeadbeef 'size try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "int")
        self.assertEqual(result._head.value, 4)

    def test_size_err(self):
        """(42 'size try) -> (err . "size of int")."""
        expr, _ = parse(tokenize("(42 'size try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "size of int")

    def test_size_underflow_err(self):
        """('size try) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("('size try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)