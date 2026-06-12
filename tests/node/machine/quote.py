import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


class TestEvaluatorQuote(unittest.TestCase):
    """quote special form — prevents evaluation."""

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

    def test_special_form_still_works(self):
        """(quote (1 2 add)) still pushes unevaluated."""
        expr, _ = parse(tokenize("(quote (1 2 add))"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsInstance(result.head, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.head.value, "little"), 1)

    def test_source_quote_pushes_unevaluated(self):
        """(quote (1 2 add)) pushes (1 2 add) without evaluating."""
        expr, _ = parse(tokenize("(quote (1 2 add))"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsInstance(result.head, Expr.Bytes)
        self.assertIsInstance(result.tail, Expr.Link)
        self.assertIsInstance(result.tail.head, Expr.Bytes)
        self.assertIsInstance(result.tail.tail, Expr.Symbol)
        self.assertEqual(result.tail.tail.value, "add")


if __name__ == "__main__":
    unittest.main(verbosity=2)
