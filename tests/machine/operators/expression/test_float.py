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


class TestFp64Operator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_fp64_from_bytes(self):
        expr, _ = parse(tokenize("(0x000000000000f03f fp64)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "fp64")
        self.assertAlmostEqual(result._value, 1.0)

    def test_fp64_from_string(self):
        expr, _ = parse(tokenize('("3.14" fp64)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "fp64")
        self.assertAlmostEqual(result._value, 3.14)

    def test_fp64_from_int(self):
        expr, _ = parse(tokenize("(42 fp64)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "fp64")
        self.assertAlmostEqual(result._value, 42.0)

    def test_fp64_identity(self):
        expr, _ = parse(tokenize("(3.14 fp64)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "fp64")
        self.assertAlmostEqual(result._value, 3.14)

    def test_fp64_non_atom_returns_nil(self):
        expr, _ = parse(tokenize("(1 2 link fp64)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_fp64_wrong_length_bytes_returns_nil(self):
        expr, _ = parse(tokenize("(0xdead fp64)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_fp64_underflow_raises(self):
        expr, _ = parse(tokenize("(fp64)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    def test_fp64_from_string_ok(self):
        expr, _ = parse(tokenize("(\"3.14\" 'fp64 try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "fp64")
        self.assertAlmostEqual(result._head._value, 3.14)

    def test_fp64_invalid_literal_err(self):
        expr, _ = parse(tokenize("(\"hello\" 'fp64 try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "fp64: invalid literal")

    def test_fp64_non_atom_err(self):
        expr, _ = parse(tokenize("(1 2 link 'fp64 try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "fp64 of link")

    def test_fp64_wrong_length_bytes_err(self):
        expr, _ = parse(tokenize("(0xdead 'fp64 try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "fp64 requires 8-byte input")

    def test_fp64_underflow_err(self):
        expr, _ = parse(tokenize("('fp64 try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)