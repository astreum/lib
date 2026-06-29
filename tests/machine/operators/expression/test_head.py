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


class TestHeadOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_head_of_link(self):
        expr, _ = parse(tokenize("(1 2 link head)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 1)

    def test_head_of_non_link_returns_nil(self):
        expr, _ = parse(tokenize('("hello" head)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_head_underflow_raises(self):
        expr, _ = parse(tokenize("(head)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    def test_head_of_link_ok(self):
        expr, _ = parse(tokenize("(1 2 link head?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._tail._tag, "int")
        self.assertEqual(result._tail.value, 1)

    def test_head_of_non_link_err(self):
        expr, _ = parse(tokenize('("hello" head?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "head of string")

    def test_head_underflow_err(self):
        expr, _ = parse(tokenize("(head?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
