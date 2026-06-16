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
        isinstance(expr, Expr.Link)
        and expr.head is not None
        and isinstance(expr.head, Expr.Symbol)
        and expr.head.value == "error"
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
        self.assertEqual(toks, ["(", '"abc"', ")"])

    def test_string_with_spaces(self):
        toks = tokenize('("hello world")')
        self.assertEqual(toks, ["(", '"hello world"', ")"])


class TestParse(unittest.TestCase):
    def test_parse_int(self):
        expr, rest = parse(["7"])
        self.assertEqual(rest, [])
        self.assertIsInstance(expr, Expr.Int)
        self.assertEqual(expr.value, 7)

    def test_parse_negative_int(self):
        expr, rest = parse(["-3"])
        self.assertEqual(rest, [])
        self.assertIsInstance(expr, Expr.Int)
        self.assertEqual(expr.value, -3)

    def test_parse_symbol(self):
        expr, rest = parse(["add"])
        self.assertEqual(rest, [])
        self.assertIsInstance(expr, Expr.Symbol)
        self.assertEqual(expr.value, "add")

    def test_parse_list_def(self):
        expr, rest = parse(tokenize("(7 x def)"))
        self.assertEqual(rest, [])
        self.assertIsInstance(expr, Expr.Link)
        # Link(Int(7), Link(Symbol("x"), Symbol("def")))
        self.assertIsInstance(expr.head, Expr.Int)
        self.assertIsInstance(expr.tail, Expr.Link)
        self.assertIsInstance(expr.tail.head, Expr.Symbol)
        self.assertEqual(expr.tail.head.value, "x")
        self.assertIsInstance(expr.tail.tail, Expr.Symbol)
        self.assertEqual(expr.tail.tail.value, "def")

    def test_parse_err_form_is_plain_list(self):
        expr, rest = parse(tokenize("(arithmetic_error err)"))
        self.assertEqual(rest, [])
        self.assertIsInstance(expr, Expr.Link)
        # Link(Symbol("arithmetic_error"), Symbol("err"))
        self.assertIsInstance(expr.head, Expr.Symbol)
        self.assertEqual(expr.head.value, "arithmetic_error")
        self.assertIsInstance(expr.tail, Expr.Symbol)
        self.assertEqual(expr.tail.value, "err")
        self.assertFalse(_is_error(expr))

    def test_parse_err_form_with_origin_is_plain_list(self):
        expr, rest = parse(tokenize("((7 0 div) arithmetic_error err)"))
        self.assertEqual(rest, [])
        self.assertIsInstance(expr, Expr.Link)
        # Link(Link(7, Link(0, div)), Link(Symbol("arithmetic_error"), Symbol("err")))
        self.assertIsInstance(expr.head, Expr.Link)  # inner (7 0 div)
        self.assertIsInstance(expr.tail, Expr.Link)
        self.assertIsInstance(expr.tail.head, Expr.Symbol)
        self.assertEqual(expr.tail.head.value, "arithmetic_error")
        self.assertIsInstance(expr.tail.tail, Expr.Symbol)
        self.assertEqual(expr.tail.tail.value, "err")
        self.assertFalse(_is_error(expr))

    def test_parse_float(self):
        expr, rest = parse(["3.14"])
        self.assertEqual(rest, [])
        self.assertIsInstance(expr, Expr.Float)
        self.assertAlmostEqual(expr.value, 3.14)

    def test_parse_hex_bytes(self):
        expr, rest = parse(["0x1f"])
        self.assertEqual(rest, [])
        self.assertIsInstance(expr, Expr.Bytes)
        self.assertEqual(expr.value, b"\x1f")

    def test_parse_string(self):
        expr, rest = parse(['"hello"'])
        self.assertEqual(rest, [])
        self.assertIsInstance(expr, Expr.String)
        self.assertEqual(expr.value, "hello")

    def test_parse_returns_rest(self):
        expr, rest = parse(tokenize("7 8"))
        self.assertIsInstance(expr, Expr.Int)
        self.assertEqual(expr.value, 7)
        self.assertEqual(rest, ["8"])

    # ---- quote parsing ----

    def test_parse_quote_postfix(self):
        """((7 3) ') — postfix quote: ' is the tail, inner list is the expression."""
        expr, rest = parse(tokenize("((7 3) ')"))
        self.assertEqual(rest, [])
        self.assertIsInstance(expr, Expr.Link)
        # Link(Link(7, 3), Symbol("'"))
        self.assertIsInstance(expr.head, Expr.Link)  # inner (7 3)
        self.assertIsInstance(expr.head.head, Expr.Int)
        self.assertIsInstance(expr.head.tail, Expr.Int)
        self.assertIsInstance(expr.tail, Expr.Symbol)
        self.assertEqual(expr.tail.value, "'")

    def test_parse_quote_symbol_inside_list(self):
        """(7 3 ') — ' inside a list is just a regular symbol, not wrapping."""
        expr, rest = parse(tokenize("(7 3 ')"))
        self.assertEqual(rest, [])
        self.assertIsInstance(expr, Expr.Link)
        # Link(Int(7), Link(Int(3), Symbol("'")))
        self.assertIsInstance(expr.head, Expr.Int)
        self.assertIsInstance(expr.tail, Expr.Link)
        self.assertIsInstance(expr.tail.head, Expr.Int)
        self.assertIsInstance(expr.tail.tail, Expr.Symbol)
        self.assertEqual(expr.tail.tail.value, "'")

    def test_parse_quote_symbol_at_toplevel(self):
        """' at top level is just a regular Symbol('\")."""
        expr, rest = parse(tokenize("'"))
        self.assertIsInstance(expr, Expr.Symbol)
        self.assertEqual(expr.value, "'")

    def test_parse_quote_keyword_is_symbol(self):
        """The token 'quote' is a plain Symbol('quote')."""
        expr, rest = parse(tokenize("quote"))
        self.assertIsInstance(expr, Expr.Symbol)
        self.assertEqual(expr.value, "quote")


if __name__ == "__main__":
    unittest.main()
