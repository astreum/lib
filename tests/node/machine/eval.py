import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


class TestEvaluatorEval(unittest.TestCase):
    """eval — evaluates whatever is on top of the stack (untyped)."""

    def setUp(self):
        self.machine = Machine(node=None)

    def _link(self, head, tail=None):
        return Expr.Link(head, tail)

    def _quote(self, body):
        return self._link(Expr.Symbol("'"), body)

    def test_eval_quoted_list(self):
        """((' (1 2 +)) eval) -> 3."""
        expr = self._link(
            self._quote(self._link(Expr.Int(1), self._link(Expr.Int(2), Expr.Symbol("+")))),
            Expr.Symbol("eval")
        )
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 3)

    def test_eval_atom_is_noop(self):
        """(42 eval) -> 42 (self-evaluating)."""
        expr, _ = parse(tokenize("(42 eval)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 42)

    def test_eval_result_of_computation(self):
        """(1 2 + eval) -> 3 (eval on already-computed value)."""
        expr = self._link(
            Expr.Int(1),
            self._link(Expr.Int(2), self._link(Expr.Symbol("+"), Expr.Symbol("eval")))
        )
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 3)

    def test_eval_inherits_stack(self):
        """(5 (' (2 +)) eval) -> 7 (body sees 5 on stack)."""
        expr = self._link(
            Expr.Int(5),
            self._link(
                self._quote(self._link(Expr.Int(2), Expr.Symbol("+"))),
                Expr.Symbol("eval")
            )
        )
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 7)

    def test_eval_chained(self):
        """((' (1 2 +)) eval 3 +) -> 6."""
        expr = self._link(
            self._quote(self._link(Expr.Int(1), self._link(Expr.Int(2), Expr.Symbol("+")))),
            self._link(Expr.Symbol("eval"), self._link(Expr.Int(3), Expr.Symbol("+")))
        )
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 6)

    def test_eval_nil_on_empty_stack(self):
        """(() eval) -> NIL."""
        expr, _ = parse(tokenize("(eval)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)

    def test_quote_symbol_then_eval(self):
        """((' x) eval) -> NIL (unbound symbol resolves to NIL)."""
        expr, _ = parse(tokenize("((' x) eval)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)


if __name__ == "__main__":
    unittest.main(verbosity=2)
