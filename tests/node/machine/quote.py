import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


class TestSpecialFormQuote(unittest.TestCase):
    """' special form — prevents evaluation."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_quote_bytes(self):
        """(' 42) -> pushes 42."""
        expr, _ = parse(tokenize("(' 42)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 42)

    def test_quote_symbol(self):
        """(' hello) -> pushes Symbol(hello), not looked up."""
        expr, _ = parse(tokenize("(' hello)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Symbol)
        self.assertEqual(result.value, "hello")

    def test_quote_list(self):
        """(' (1 2 3)) -> pushes the whole list unevaluated."""
        expr, _ = parse(tokenize("(' (1 2 3))"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)

    def test_quote_with_no_arg(self):
        """(') -> pushes NIL."""
        expr, _ = parse(tokenize("(')"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_special_form_still_works(self):
        """(' (1 2 add)) still pushes unevaluated."""
        expr, _ = parse(tokenize("(' (1 2 add))"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsInstance(result.head, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.head.value, "little"), 1)

    def test_source_quote_pushes_unevaluated(self):
        """(' (1 2 add)) pushes (1 2 add) without evaluating."""
        expr, _ = parse(tokenize("(' (1 2 add))"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsInstance(result.head, Expr.Bytes)
        self.assertIsInstance(result.tail, Expr.Link)
        self.assertIsInstance(result.tail.head, Expr.Bytes)
        self.assertIsInstance(result.tail.tail, Expr.Symbol)
        self.assertEqual(result.tail.tail.value, "add")


class TestQuoteOperator(unittest.TestCase):
    """quote stack operator — wraps top of stack in (' ...)."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_quote_wraps_bytes(self):
        """(42 quote) -> (' 42)."""
        expr, _ = parse(tokenize("(42 quote)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsInstance(result.head, Expr.Symbol)
        self.assertEqual(result.head.value, "'")
        self.assertIsInstance(result.tail, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.tail.value, "little"), 42)

    def test_quote_wraps_unbound_variable_as_nil(self):
        """(hello quote) -> hello is unbound → NIL → (' NIL)."""
        expr, _ = parse(tokenize("(hello quote)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsInstance(result.head, Expr.Symbol)
        self.assertEqual(result.head.value, "'")
        self.assertIsInstance(result.tail, Expr.Link)
        self.assertIsNone(result.tail.head)
        self.assertIsNone(result.tail.tail)

    def test_quote_wraps_quoted_symbol(self):
        """((' hello) quote) -> wraps the quoted symbol -> (' hello)."""
        expr, _ = parse(tokenize("((' hello) quote)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsInstance(result.head, Expr.Symbol)
        self.assertEqual(result.head.value, "'")
        self.assertIsInstance(result.tail, Expr.Symbol)
        self.assertEqual(result.tail.value, "hello")

    def test_quote_wraps_list_result(self):
        """((1 2 add) quote) -> (' 3)."""
        expr, _ = parse(tokenize("((1 2 add) quote)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsInstance(result.head, Expr.Symbol)
        self.assertEqual(result.head.value, "'")
        self.assertIsInstance(result.tail, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.tail.value, "little"), 3)

    def test_quote_then_eval(self):
        """((' 42) eval) -> returns 42."""
        expr, _ = parse(tokenize("((' 42) eval)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 42)

if __name__ == "__main__":
    unittest.main(verbosity=2)
