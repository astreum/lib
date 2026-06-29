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


class TestIndexOperator(unittest.TestCase):
    """index operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare index ---

    def test_index(self):
        """(0xdeadbeef 0 index) -> 0xde."""
        expr, _ = parse(tokenize("(0xdeadbeef 0 index)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\xde")

    def test_index_non_bytes_returns_nil(self):
        """("hello" 0 index) -> NIL (type mismatch)."""
        expr, _ = parse(tokenize('("hello" 0 index)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_index_out_of_bounds_returns_nil(self):
        """(0xdead 5 index) -> NIL (out of bounds)."""
        expr, _ = parse(tokenize("(0xdead 5 index)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_index_underflow_raises(self):
        """(index) raises IndexError."""
        expr, _ = parse(tokenize("(index)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    # --- tagged index (?) ---

    def test_index_ok(self):
        """(0xdeadbeef 0 index?) -> (ok . 0xde)."""
        expr, _ = parse(tokenize("(0xdeadbeef 0 index?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._tail._tag, "bytes")
        self.assertEqual(result._tail.value, b"\xde")

    def test_index_type_err(self):
        """("hello" 0 index?) -> (err . "index of string by int")."""
        expr, _ = parse(tokenize('("hello" 0 index?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "index of string by int")

    def test_index_oob_err(self):
        """(0xdead 5 index?) -> (err . "index 5 out of bounds for bytes of length 2")."""
        expr, _ = parse(tokenize("(0xdead 5 index?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "index 5 out of bounds for bytes of length 2")

    def test_index_underflow_err(self):
        """(index?) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("(index?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
