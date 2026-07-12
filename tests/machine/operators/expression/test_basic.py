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


class TestLinkOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_link(self):
        expr, _ = parse(tokenize("(1 2 link)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")

    def test_link_ok(self):
        expr, _ = parse(tokenize("(1 2 link?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "link")

    def test_link_underflow_err(self):
        expr, _ = parse(tokenize("(link?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head.value, "stack underflow")



class TestIsEqOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_is_eq_same(self):
        expr, _ = parse(tokenize("(1 1 is_eq)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\x01")

    def test_is_eq_different(self):
        expr, _ = parse(tokenize("(1 2 is_eq)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\x00")

    def test_is_eq_ok(self):
        expr, _ = parse(tokenize("(1 1 is_eq?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))

    def test_is_eq_underflow_err(self):
        expr, _ = parse(tokenize("(is_eq?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head.value, "stack underflow")


class TestQuoteOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_quote(self):
        expr, _ = parse(tokenize("(42 quote)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertEqual(result._head._tag, "symbol")
        self.assertEqual(result._head.value, "'")

    def test_quote_ok(self):
        expr, _ = parse(tokenize("(42 quote?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "link")
        self.assertEqual(result._head._head._tag, "symbol")
        self.assertEqual(result._head._head.value, "'")

    def test_quote_underflow_err(self):
        expr, _ = parse(tokenize("(quote?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head.value, "stack underflow")


class TestEvalOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_eval(self):
        expr, _ = parse(tokenize("((1 2 +) eval)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 3)

    def test_eval_ok(self):
        expr, _ = parse(tokenize("((1 2 +) eval?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "int")
        self.assertEqual(result._head.value, 3)

    def test_eval_empty_returns_nil(self):
        expr, _ = parse(tokenize("(eval)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)


if __name__ == "__main__":
    unittest.main(verbosity=2)