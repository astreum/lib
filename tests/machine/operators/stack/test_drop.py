import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


def _is_tagged(expr, tag):
    return (
        expr._tag == "link"
        and expr._tail is not None
        and expr._tail._tag == "symbol"
        and expr._tail.value == tag
    )


def _is_nil(expr):
    return expr._tag == "link" and expr._head is None and expr._tail is None


class TestDropOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_drop_removes_top(self):
        expr, _ = parse(tokenize("(1 2 drop)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 1)

    def test_drop_ok_nil(self):
        expr, _ = parse(tokenize("(1 drop?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertTrue(_is_nil(result._head))

    def test_drop_underflow_returns_nil(self):
        expr, _ = parse(tokenize("(drop)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_nil(result))

    def test_drop_underflow_err(self):
        expr, _ = parse(tokenize("(drop?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)