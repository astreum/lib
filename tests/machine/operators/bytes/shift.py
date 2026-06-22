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


# --- << operator ---

class TestShiftOperator(unittest.TestCase):
    """<< shift operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_shift_bytes_left(self):
        expr, _ = parse(tokenize("(0x01 2 <<)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x04")

    def test_shift_bytes_right_negative(self):
        expr, _ = parse(tokenize("(0x04 -2 <<)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x01")

    def test_shift_bytes_zero(self):
        expr, _ = parse(tokenize("(0xab 0 <<)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\xab")

    def test_shift_int_left(self):
        expr, _ = parse(tokenize("(42 2 <<)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 168)

    def test_shift_int_right_negative(self):
        expr, _ = parse(tokenize("(42 -2 <<)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 10)

    def test_shift_int_zero(self):
        expr, _ = parse(tokenize("(42 0 <<)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 42)

    def test_shift_type_err_returns_nil(self):
        expr, _ = parse(tokenize('("hi" 2 <<)'))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_shift_underflow_raises(self):
        expr, _ = parse(tokenize("(<<)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    def test_shift_bytes_left_ok(self):
        expr, _ = parse(tokenize("(0x01 2 <<?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Bytes)
        self.assertEqual(result.tail.value, b"\x04")

    def test_shift_bytes_right_negative_ok(self):
        expr, _ = parse(tokenize("(0x04 -2 <<?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Bytes)
        self.assertEqual(result.tail.value, b"\x01")

    def test_shift_int_left_ok(self):
        expr, _ = parse(tokenize("(42 2 <<?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Int)
        self.assertEqual(result.tail.value, 168)

    def test_shift_type_err(self):
        expr, _ = parse(tokenize('("hi" 2 <<?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "shift of string by int")

    def test_shift_amount_err(self):
        expr, _ = parse(tokenize("(0x01 \"hi\" <<?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "shift of bytes by string")

    def test_shift_underflow_err(self):
        expr, _ = parse(tokenize("(<<?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "stack underflow")


# --- <<< operator ---

class TestRotateOperator(unittest.TestCase):
    """<<< rotate operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_rotate_bytes_left(self):
        expr, _ = parse(tokenize("(0x01 2 <<<)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x04")

    def test_rotate_bytes_right_negative(self):
        expr, _ = parse(tokenize("(0x01 -2 <<<)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x40")

    def test_rotate_bytes_zero(self):
        expr, _ = parse(tokenize("(0xab 0 <<<)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\xab")

    def test_rotate_bytes_full_wrap(self):
        expr, _ = parse(tokenize("(0x01 8 <<<)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x01")

    def test_rotate_int_left(self):
        expr, _ = parse(tokenize("(1 2 <<<)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 4)

    def test_rotate_int_right_negative(self):
        expr, _ = parse(tokenize("(1 -2 <<<)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 64)

    def test_rotate_int_zero(self):
        expr, _ = parse(tokenize("(42 0 <<<)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 42)

    def test_rotate_int_signed_preserved(self):
        expr, _ = parse(tokenize("(-1 4 <<<)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, -1)

    def test_rotate_type_err_returns_nil(self):
        expr, _ = parse(tokenize('("hi" 2 <<<)'))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_rotate_underflow_raises(self):
        expr, _ = parse(tokenize("(<<<)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    def test_rotate_bytes_left_ok(self):
        expr, _ = parse(tokenize("(0x01 2 <<<?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Bytes)
        self.assertEqual(result.tail.value, b"\x04")

    def test_rotate_bytes_right_negative_ok(self):
        expr, _ = parse(tokenize("(0x01 -2 <<<?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Bytes)
        self.assertEqual(result.tail.value, b"\x40")

    def test_rotate_int_left_ok(self):
        expr, _ = parse(tokenize("(1 2 <<<?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Int)
        self.assertEqual(result.tail.value, 4)

    def test_rotate_type_err(self):
        expr, _ = parse(tokenize('("hi" 2 <<<?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "rotate of string by int")

    def test_rotate_amount_err(self):
        expr, _ = parse(tokenize("(0x01 \"hi\" <<<?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "rotate of bytes by string")

    def test_rotate_underflow_err(self):
        expr, _ = parse(tokenize("(<<<?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
