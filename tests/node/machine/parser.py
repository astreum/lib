import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, ParseError, tokenize, parse  # noqa: E402


def _is_error(expr):
    return (
        isinstance(expr, Expr.ListExpr)
        and bool(expr.elements)
        and isinstance(expr.elements[0], Expr.Symbol)
        and expr.elements[0].value == "error"
    )


class TestTokenize(unittest.TestCase):
    def test_basic_tokens(self):
        self.assertEqual(tokenize("(1 2 add)"), ["(", "1", "2", "add", ")"])

    def test_whitespace_and_newlines(self):
        src = """
        (  7
  x   def )
        """
        toks = tokenize(src)
        self.assertEqual(toks, ["(", "7", "x", "def", ")"])

    def test_quotes_are_tokenized(self):
        toks = tokenize('("abc")')
        self.assertIn('"abc"', toks)


class TestParse(unittest.TestCase):
    def test_parse_byte(self):
        expr, rest = parse(["7"])
        self.assertEqual(rest, [])
        self.assertIsInstance(expr, Expr.Bytes)
        self.assertEqual(expr.value, b"\x07")

    def test_parse_symbol(self):
        expr, rest = parse(["add"])
        self.assertEqual(rest, [])
        self.assertIsInstance(expr, Expr.Symbol)
        self.assertEqual(expr.value, "add")

    def test_parse_list_def(self):
        expr, rest = parse(tokenize("(7 x def)"))
        self.assertEqual(rest, [])
        self.assertIsInstance(expr, Expr.ListExpr)
        self.assertEqual(len(expr.elements), 3)
        self.assertIsInstance(expr.elements[0], Expr.Bytes)
        self.assertIsInstance(expr.elements[1], Expr.Symbol)
        self.assertIsInstance(expr.elements[2], Expr.Symbol)

    def test_parse_err_form_is_plain_list(self):
        expr, rest = parse(tokenize("(arithmetic_error err)"))
        self.assertEqual(rest, [])
        self.assertIsInstance(expr, Expr.ListExpr)
        self.assertEqual(len(expr.elements), 2)
        self.assertTrue(all(isinstance(el, Expr.Symbol) for el in expr.elements))
        self.assertEqual([el.value for el in expr.elements], ["arithmetic_error", "err"])
        self.assertFalse(_is_error(expr))

    def test_parse_err_form_with_origin_is_plain_list(self):
        expr, rest = parse(tokenize("((7 0 div) arithmetic_error err)"))
        self.assertEqual(rest, [])
        self.assertIsInstance(expr, Expr.ListExpr)
        self.assertEqual(len(expr.elements), 3)
        self.assertIsInstance(expr.elements[0], Expr.ListExpr)
        self.assertTrue(all(isinstance(el, Expr.Symbol) for el in expr.elements[1:]))
        self.assertEqual(expr.elements[1].value, "arithmetic_error")
        self.assertEqual(expr.elements[2].value, "err")
        self.assertFalse(_is_error(expr))

    def test_parse_returns_rest(self):
        expr, rest = parse(tokenize("7 8"))
        self.assertIsInstance(expr, Expr.Bytes)
        self.assertEqual(expr.value, b"\x07")
        self.assertEqual(rest, ["8"])

    # ---- quote parsing ----

    def test_parse_quote_postfix(self):
        """((7 3) ') — postfix quote: ' is the tail, inner list is the expression."""
        expr, rest = parse(tokenize("((7 3) ')"))
        self.assertEqual(rest, [])
        self.assertIsInstance(expr, Expr.ListExpr)
        self.assertEqual(len(expr.elements), 2)
        self.assertIsInstance(expr.elements[0], Expr.ListExpr)
        self.assertEqual(len(expr.elements[0].elements), 2)
        self.assertIsInstance(expr.elements[1], Expr.Symbol)
        self.assertEqual(expr.elements[1].value, "'")

    def test_parse_quote_symbol_inside_list(self):
        """(7 3 ') — ' inside a list is just a regular symbol, not wrapping."""
        expr, rest = parse(tokenize("(7 3 ')"))
        self.assertEqual(rest, [])
        self.assertIsInstance(expr, Expr.ListExpr)
        self.assertEqual(len(expr.elements), 3)
        self.assertIsInstance(expr.elements[0], Expr.Bytes)
        self.assertIsInstance(expr.elements[1], Expr.Bytes)
        self.assertIsInstance(expr.elements[2], Expr.Symbol)
        self.assertEqual(expr.elements[2].value, "'")

    def test_parse_quote_symbol_at_toplevel(self):
        """' at top level is just a regular Symbol('\")."""
        expr, rest = parse(tokenize("'"))
        self.assertIsInstance(expr, Expr.Symbol)
        self.assertEqual(expr.value, "'")

    def test_parse_quote_normalized_from_quote_token(self):
        """The token 'quote' normalizes to the ' symbol."""
        expr, rest = parse(tokenize("quote"))
        self.assertIsInstance(expr, Expr.Symbol)
        self.assertEqual(expr.value, "'")


if __name__ == "__main__":
    unittest.main()
