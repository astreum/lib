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


class TestIntOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_int_from_bytes(self):
        expr, _ = parse(tokenize("(0x2a int)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 42)

    def test_int_from_string(self):
        expr, _ = parse(tokenize('("42" int)'))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 42)

    def test_int_from_float(self):
        expr, _ = parse(tokenize("(3.14 int)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 3)

    def test_int_identity(self):
        expr, _ = parse(tokenize("(42 int)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 42)

    def test_int_non_atom_returns_nil(self):
        expr, _ = parse(tokenize("(1 2 link int)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_int_underflow_raises(self):
        expr, _ = parse(tokenize("(int)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    def test_int_from_string_ok(self):
        expr, _ = parse(tokenize('("42" int?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Int)
        self.assertEqual(result.tail.value, 42)

    def test_int_invalid_literal_err(self):
        expr, _ = parse(tokenize('("hello" int?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "int: invalid literal")

    def test_int_non_atom_err(self):
        expr, _ = parse(tokenize("(1 2 link int?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "int of link")

    def test_int_underflow_err(self):
        expr, _ = parse(tokenize("(int?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
