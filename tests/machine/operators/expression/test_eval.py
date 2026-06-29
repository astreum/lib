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
        and expr._head._tag == "symbol"
        and expr._head.value == tag
    )


class TestEvalOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_underflow_bare(self):
        expr, _ = parse(tokenize("(eval)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_underflow_tagged(self):
        expr, _ = parse(tokenize("(eval?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "stack underflow")

    def test_success_bare(self):
        expr, _ = parse(tokenize("('(1 2 +) eval)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 3)

    def test_success_tagged(self):
        expr, _ = parse(tokenize("('(1 2 +) eval?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._tail._tag, "int")
        self.assertEqual(result._tail.value, 3)

    def test_eval_result_of_computation(self):
        expr, _ = parse(tokenize("(1 2 + eval)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 3)

    def test_eval_inherits_stack(self):
        expr, _ = parse(tokenize("(5 '(2 +) eval)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 7)

    def test_eval_chained(self):
        expr, _ = parse(tokenize("('(1 2 +) eval 3 +)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 6)

    def test_eval_quoted_unbound_symbol(self):
        expr, _ = parse(tokenize("((' x) eval)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
