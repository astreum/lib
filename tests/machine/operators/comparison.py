import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
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


class TestComparisonOperators(unittest.TestCase):
    """Comparison operators (< > <= >=) — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare less than ---

    def test_lt_int_true(self):
        """(2 3 <) -> Bytes(\\x01)."""
        expr, _ = parse(tokenize("(2 3 <)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\x01")

    def test_lt_float_true(self):
        """(2.0 3.0 <) -> Bytes(\\x01)."""
        expr, _ = parse(tokenize("(2.0 3.0 <)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\x01")

    # --- bare greater than ---

    def test_gt_int_true(self):
        """(3 2 >) -> Bytes(\\x01)."""
        expr, _ = parse(tokenize("(3 2 >)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\x01")

    def test_gt_float_true(self):
        """(2.0 1.5 >) -> Bytes(\\x01)."""
        expr, _ = parse(tokenize("(2.0 1.5 >)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\x01")

    # --- bare less than or equal ---

    def test_le_int_true(self):
        """(2 2 <=) -> Bytes(\\x01)."""
        expr, _ = parse(tokenize("(2 2 <=)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\x01")

    def test_le_int_false(self):
        """(3 2 <=) -> Bytes(\\x00)."""
        expr, _ = parse(tokenize("(3 2 <=)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\x00")

    def test_le_float_true(self):
        """(2.0 2.0 <=) -> Bytes(\\x01)."""
        expr, _ = parse(tokenize("(2.0 2.0 <=)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\x01")

    # --- bare greater than or equal ---

    def test_ge_int_true(self):
        """(2 2 >=) -> Bytes(\\x01)."""
        expr, _ = parse(tokenize("(2 2 >=)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\x01")

    def test_ge_int_false(self):
        """(2 3 >=) -> Bytes(\\x00)."""
        expr, _ = parse(tokenize("(2 3 >=)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\x00")

    def test_ge_float_true(self):
        """(2.0 2.0 >=) -> Bytes(\\x01)."""
        expr, _ = parse(tokenize("(2.0 2.0 >=)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\x01")

    # --- bare cross-type errors -> NIL ---

    def test_lt_cross_type_returns_nil(self):
        """(2 3.0 <) -> NIL."""
        expr, _ = parse(tokenize("(2 3.0 <)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_gt_cross_type_returns_nil(self):
        """(2.0 3 >) -> NIL."""
        expr, _ = parse(tokenize("(2.0 3 >)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_le_cross_type_returns_nil(self):
        """(\"a\" 3 <=) -> NIL."""
        expr, _ = parse(tokenize('("a" 3 <=)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_ge_cross_type_returns_nil(self):
        """(3 \"a\" >=) -> NIL."""
        expr, _ = parse(tokenize('(3 "a" >=)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    # --- bare underflow -> IndexError ---

    def test_lt_underflow_raises(self):
        """(<) -> IndexError."""
        expr, _ = parse(tokenize("(<)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    def test_gt_underflow_raises(self):
        """(>) -> IndexError."""
        expr, _ = parse(tokenize("(>)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    # --- tagged (<?) ---

    def test_lt_int_ok(self):
        """(2 3 <? ) -> (ok . Bytes(\\x01))."""
        expr, _ = parse(tokenize("(2 3 <? )"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "bytes")
        self.assertEqual(result._head.value, b"\x01")

    def test_lt_cross_type_err(self):
        """(2 3.0 <? ) -> (err . \"less than of int and float\")."""
        expr, _ = parse(tokenize("(2 3.0 <? )"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "less than of int and float")

    def test_lt_underflow_err(self):
        """(<? ) -> (err . \"stack underflow\")."""
        expr, _ = parse(tokenize("(<? )"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "stack underflow")

    # --- tagged (>?) ---

    def test_gt_int_ok(self):
        """(3 2 >?) -> (ok . Bytes(\\x01))."""
        expr, _ = parse(tokenize("(3 2 >?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "bytes")
        self.assertEqual(result._head.value, b"\x01")

    def test_gt_cross_type_err(self):
        """(2.0 3 >?) -> (err . \"greater than of float and int\")."""
        expr, _ = parse(tokenize("(2.0 3 >?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "greater than of float and int")

    def test_gt_underflow_err(self):
        """(>?) -> (err . \"stack underflow\")."""
        expr, _ = parse(tokenize("(>?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "stack underflow")

    # --- tagged (<=?) ---

    def test_le_int_ok(self):
        """(2 2 <=?) -> (ok . Bytes(\\x01))."""
        expr, _ = parse(tokenize("(2 2 <=?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "bytes")
        self.assertEqual(result._head.value, b"\x01")

    def test_le_cross_type_err(self):
        """(\"a\" 3 <=?) -> (err . \"less than or equal of string and int\")."""
        expr, _ = parse(tokenize('("a" 3 <=?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "less than or equal of str and int")

    # --- tagged (>=?) ---

    def test_ge_int_ok(self):
        """(2 2 >=?) -> (ok . Bytes(\\x01))."""
        expr, _ = parse(tokenize("(2 2 >=?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "bytes")
        self.assertEqual(result._head.value, b"\x01")

    def test_ge_cross_type_err(self):
        """(3 \"a\" >=?) -> (err . \"greater than or equal of int and string\")."""
        expr, _ = parse(tokenize('(3 "a" >=?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "greater than or equal of int and str")


if __name__ == "__main__":
    unittest.main(verbosity=2)
