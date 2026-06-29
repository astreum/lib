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


class TestFloatOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_float_from_bytes(self):
        expr, _ = parse(tokenize("(0x000000000000f03f float)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "float")
        self.assertAlmostEqual(result.value, 1.0)

    def test_float_from_string(self):
        expr, _ = parse(tokenize('("3.14" float)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "float")
        self.assertAlmostEqual(result.value, 3.14)

    def test_float_from_int(self):
        expr, _ = parse(tokenize("(42 float)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "float")
        self.assertAlmostEqual(result.value, 42.0)

    def test_float_identity(self):
        expr, _ = parse(tokenize("(3.14 float)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "float")
        self.assertAlmostEqual(result.value, 3.14)

    def test_float_non_atom_returns_nil(self):
        expr, _ = parse(tokenize("(1 2 link float)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_float_wrong_length_bytes_returns_nil(self):
        expr, _ = parse(tokenize("(0xdead float)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_float_underflow_raises(self):
        expr, _ = parse(tokenize("(float)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    def test_float_from_string_ok(self):
        expr, _ = parse(tokenize('("3.14" float?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._tail._tag, "float")
        self.assertAlmostEqual(result._tail.value, 3.14)

    def test_float_invalid_literal_err(self):
        expr, _ = parse(tokenize('("hello" float?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "float: invalid literal")

    def test_float_non_atom_err(self):
        expr, _ = parse(tokenize("(1 2 link float?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "float of link")

    def test_float_wrong_length_bytes_err(self):
        expr, _ = parse(tokenize("(0xdead float?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "float requires 8-byte input")

    def test_float_underflow_err(self):
        expr, _ = parse(tokenize("(float?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
