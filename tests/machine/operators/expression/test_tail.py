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


class TestTailOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_tail_of_link(self):
        expr, _ = parse(tokenize("(1 2 link tail)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 2)

    def test_tail_of_non_link_returns_nil(self):
        expr, _ = parse(tokenize('("hello" tail)'))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_tail_underflow_raises(self):
        expr, _ = parse(tokenize("(tail)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    def test_tail_of_link_ok(self):
        expr, _ = parse(tokenize("(1 2 link tail?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Int)
        self.assertEqual(result.tail.value, 2)

    def test_tail_of_non_link_err(self):
        expr, _ = parse(tokenize('("hello" tail?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "tail of string")

    def test_tail_underflow_err(self):
        expr, _ = parse(tokenize("(tail?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
