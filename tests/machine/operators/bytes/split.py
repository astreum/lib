import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine
from astreum.machine.models.expression import NIL


def _is_tagged(expr, tag):
    return (
        isinstance(expr, Expr.Link)
        and isinstance(expr.head, Expr.Symbol)
        and expr.head.value == tag
    )


class TestSplitOperator(unittest.TestCase):
    """split operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare split ---

    def test_split(self):
        """(0xdeadbeef 2 split) -> Link(left, right)."""
        expr, _ = parse(tokenize("(0xdeadbeef 2 split)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsInstance(result.head, Expr.Bytes)
        self.assertEqual(result.head.value, b"\xde\xad")
        self.assertIsInstance(result.tail, Expr.Bytes)
        self.assertEqual(result.tail.value, b"\xbe\xef")

    def test_split_left_kept_by_head(self):
        expr, _ = parse(tokenize("(0xabcdef 1 split head)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\xab")

    def test_split_at_zero(self):
        expr, _ = parse(tokenize("(0xabcdef 0 split)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsInstance(result.head, Expr.Bytes)
        self.assertEqual(result.head.value, b"")
        self.assertIsInstance(result.tail, Expr.Bytes)
        self.assertEqual(result.tail.value, b"\xab\xcd\xef")

    def test_split_at_full_length(self):
        expr, _ = parse(tokenize("(0xabcdef 3 split)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsInstance(result.head, Expr.Bytes)
        self.assertEqual(result.head.value, b"\xab\xcd\xef")
        self.assertIsInstance(result.tail, Expr.Bytes)
        self.assertEqual(result.tail.value, b"")

    def test_split_non_bytes_returns_nil(self):
        """("hello" 0 split) -> NIL (type mismatch)."""
        expr, _ = parse(tokenize('("hello" 0 split)'))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_split_out_of_bounds_returns_nil(self):
        """(0xdead 5 split) -> NIL (out of bounds)."""
        expr, _ = parse(tokenize("(0xdead 5 split)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_split_underflow_raises(self):
        """(split) raises IndexError."""
        expr, _ = parse(tokenize("(split)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    # --- tagged split (?) ---

    def test_split_ok(self):
        """(0xdeadbeef 2 split?) -> (ok . Link(left, right))."""
        expr, _ = parse(tokenize("(0xdeadbeef 2 split?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Link)
        self.assertIsInstance(result.tail.head, Expr.Bytes)
        self.assertEqual(result.tail.head.value, b"\xde\xad")
        self.assertIsInstance(result.tail.tail, Expr.Bytes)
        self.assertEqual(result.tail.tail.value, b"\xbe\xef")

    def test_split_type_err(self):
        """("hello" 0 split?) -> (err . "split of string at int")."""
        expr, _ = parse(tokenize('("hello" 0 split?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "split of string at int")

    def test_split_oob_err(self):
        """(0xdead 5 split?) -> (err . "split index 5 out of bounds for bytes of length 2")."""
        expr, _ = parse(tokenize("(0xdead 5 split?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(
            result.tail.value, "split index 5 out of bounds for bytes of length 2"
        )

    def test_split_underflow_err(self):
        """(split?) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("(split?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
