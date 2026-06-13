import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


class TestEvaluatorDefAndLookup(unittest.TestCase):
    """def binding and symbol resolution."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_def_then_lookup_resolves(self):
        """((7 (quote seven) def) seven) -> stack has [7]."""
        expr, _ = parse(tokenize("((7 (quote seven) def) seven)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 7)

    def test_def_overwrites(self):
        """((5 (quote x) def) (99 (quote x) def) x) -> write-once: first def wins."""
        expr, _ = parse(tokenize("((5 (quote x) def) (99 (quote x) def) x)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 5)

    def test_unbound_symbol_yields_nil(self):
        """An undefined symbol pushes nil (Link(None,None))."""
        expr, _ = parse(tokenize("undefined_symbol"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)


class TestEvaluatorEnvScoping(unittest.TestCase):
    """Environment scoping for lambda, fn, and def."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_def_inside_lambda_does_not_leak(self):
        """lambda: (def x) writes to ephemeral env; global x unchanged."""
        expr, _ = parse(tokenize(
            "((5 (quote x) def) "
            "(0 (quote ($0)) (quote ((99 (quote x) def) $0)) lambda) "
            "x)"
        ))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 5)

    def test_def_inside_fn_writes_to_global(self):
        """fn: (def y) writes to global_env via def_target."""
        expr, _ = parse(tokenize(
            "((0 (quote ($0)) (quote ((42 (quote y) def) $0)) fn) y)"
        ))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 42)

    def test_lambda_cannot_read_outer_vars(self):
        """lambda: parent=None, outer var returns nil."""
        expr, _ = parse(tokenize(
            "((99 (quote outer) def) "
            "(0 (quote ($0)) (quote outer) lambda))"
        ))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_fn_can_read_outer_vars(self):
        """fn: parent=env, outer var is visible."""
        expr, _ = parse(tokenize(
            "((99 (quote outer_val) def) "
            "(0 (quote ($0)) (quote outer_val) fn))"
        ))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 99)


if __name__ == "__main__":
    unittest.main(verbosity=2)
