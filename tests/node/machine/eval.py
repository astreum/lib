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

    def test_eval_quoted_list(self):
        """((quote (1 2 add)) eval) -> 3."""
        expr, _ = parse(tokenize("((quote (1 2 add)) eval)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 3)

    def test_eval_atom_is_noop(self):
        """(42 eval) -> 42 (self-evaluating)."""
        expr, _ = parse(tokenize("(42 eval)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 42)

    def test_eval_result_of_computation(self):
        """(1 2 add eval) -> 3 (eval on already-computed value)."""
        expr, _ = parse(tokenize("(1 2 add eval)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 3)

    def test_eval_inherits_stack(self):
        """(5 (quote (2 add)) eval) -> 7 (body sees 5 on stack)."""
        expr, _ = parse(tokenize("(5 (quote (2 add)) eval)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 7)

    def test_eval_chained(self):
        """((quote (1 2 add)) eval 3 add) -> 6."""
        expr, _ = parse(tokenize("((quote (1 2 add)) eval 3 add)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 6)

    def test_eval_nil_on_empty_stack(self):
        """(() eval) -> NIL."""
        expr, _ = parse(tokenize("(eval)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)

    def test_quote_symbol_then_eval(self):
        """((quote x) eval) -> NIL (unbound symbol resolves to NIL)."""
        expr, _ = parse(tokenize("((quote x) eval)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)


if __name__ == "__main__":
    unittest.main(verbosity=2)
