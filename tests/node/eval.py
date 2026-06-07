"""Tests for the unified evaluator via Machine.run().

Exercise the core evaluation loop: symbol resolution, def binding, fn application,
conditionals, quoting, and arithmetic.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse  # noqa: E402
from astreum.machine.main import Machine  # noqa: E402


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
        """((5 (quote x) def) (99 (quote x) def) x) -> second def wins."""
        expr, _ = parse(tokenize("((5 (quote x) def) (99 (quote x) def) x)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 99)

    def test_unbound_symbol_yields_nil(self):
        """An undefined symbol pushes nil (Link(None,None))."""
        expr, _ = parse(tokenize("undefined_symbol"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)


class TestEvaluatorFn(unittest.TestCase):
    """fn — inline function application.
    
    fn pops: body (top), then params (next). So the expression order is:
    (args... (quote params) (quote body) fn)
    """

    def setUp(self):
        self.machine = Machine(node=None)

    def test_fn_add_two_numbers(self):
        """(3 5 (quote ($0 $1)) (quote ($0 $1 +)) fn) -> 8."""
        expr, _ = parse(tokenize("(3 5 (quote ($0 $1)) (quote ($0 $1 +)) fn)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 8)

    def test_fn_three_args(self):
        """(10 20 30 (quote ($0 $1 $2)) (quote ($0 $1 $2 + +)) fn) -> 60."""
        expr, _ = parse(tokenize(
            "(10 20 30 (quote ($0 $1 $2)) (quote ($0 $1 $2 + +)) fn)"
        ))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 60)

    def test_fn_nested_call(self):
        """((3 5 (quote ($0 $1)) (quote ($0 $1 +)) fn) 2 +) -> 10."""
        expr, _ = parse(tokenize(
            "((3 5 (quote ($0 $1)) (quote ($0 $1 +)) fn) 2 +)"
        ))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 10)


class TestEvaluatorIf(unittest.TestCase):
    """if — conditional evaluation."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_if_truthy_takes_first_branch(self):
        """(1 (quote 42) (quote 0) if) -> 42 (truthy picks else/first)."""
        expr, _ = parse(tokenize("(1 (quote 42) (quote 0) if)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 42)

    def test_if_falsy_takes_second_branch(self):
        """(0 (quote 42) (quote 99) if) -> 99 (falsy picks then/second)."""
        expr, _ = parse(tokenize("(0 (quote 42) (quote 99) if)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 99)

    def test_if_with_computation(self):
        """(1 (2 3 +) (quote 0) if) -> 5 (evaluates the branch)."""
        expr, _ = parse(tokenize("(1 (2 3 +) (quote 0) if)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(int.from_bytes(result.value, "little"), 5)


class TestEvaluatorQuote(unittest.TestCase):
    """quote — prevents evaluation."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_quote_bytes(self):
        """(quote 42) -> pushes 42."""
        expr, _ = parse(tokenize("(quote 42)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 42)

    def test_quote_symbol(self):
        """(quote hello) -> pushes Symbol(hello), not looked up."""
        expr, _ = parse(tokenize("(quote hello)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Symbol)
        self.assertEqual(result.value, "hello")

    def test_quote_list(self):
        """(quote (1 2 3)) -> pushes the whole list unevaluated."""
        expr, _ = parse(tokenize("(quote (1 2 3))"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)

    def test_quote_with_no_arg(self):
        """(quote) -> pushes NIL."""
        expr, _ = parse(tokenize("(quote)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)


class TestEvaluatorArithmetic(unittest.TestCase):
    """+, *, and / operators."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_add(self):
        """(10 20 +) -> 30."""
        expr, _ = parse(tokenize("(10 20 +)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(int.from_bytes(result.value, "little"), 30)

    def test_add_overflow(self):
        """(255 1 +) -> 256 (no masking, variable-length encoding)."""
        expr, _ = parse(tokenize("(255 1 +)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertGreater(int.from_bytes(result.value, "little"), 255)

    def test_mul(self):
        """(7 8 *) -> 56."""
        expr, _ = parse(tokenize("(7 8 *)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 56)

    def test_div(self):
        """(100 7 /) -> 14."""
        expr, _ = parse(tokenize("(100 7 /)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 14)

class TestEvaluatorIsEq(unittest.TestCase):
    """is_eq — structural equality."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_is_eq_equal(self):
        """(42 42 is_eq) -> 1."""
        expr, _ = parse(tokenize("(42 42 is_eq)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(int.from_bytes(result.value, "little"), 1)

    def test_is_eq_not_equal(self):
        """(42 99 is_eq) -> 0."""
        expr, _ = parse(tokenize("(42 99 is_eq)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(int.from_bytes(result.value, "little"), 0)

    def test_is_eq_combined_with_if(self):
        """((42 42 is_eq) (quote (quote yes)) (quote (quote no)) if) -> Symbol(yes)."""
        expr, _ = parse(tokenize("((42 42 is_eq) (quote (quote yes)) (quote (quote no)) if)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Symbol)
        self.assertEqual(result.value, "yes")


class TestEvaluatorLinkOps(unittest.TestCase):
    """link, head, tail — list construction and deconstruction."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_link_constructs_pair(self):
        """(1 2 link) -> Link(1, 2)."""
        expr, _ = parse(tokenize("(1 2 link)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsInstance(result.head, Expr.Bytes)
        self.assertIsInstance(result.tail, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.head.value, "little"), 1)
        self.assertEqual(int.from_bytes(result.tail.value, "little"), 2)

    def test_head_extracts_first(self):
        """((1 2 link) head) -> 1."""
        expr, _ = parse(tokenize("((1 2 link) head)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 1)

    def test_tail_extracts_second(self):
        """((1 2 link) tail) -> 2."""
        expr, _ = parse(tokenize("((1 2 link) tail)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
