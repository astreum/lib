import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, ParseError, tokenize, parse  # noqa: E402
from astreum.expression import NIL  # noqa: E402


def _is_error(expr):
    return (
        expr._tag == "link"
        and expr._head is not None
        and expr._head._tag == "symbol"
        and expr._head.value == "error"
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
        self.assertEqual(expr._tag, "int")
        self.assertEqual(expr.value, 7)

    def test_parse_negative_int(self):
        expr, rest = parse(["-3"])
        self.assertEqual(rest, [])
        self.assertEqual(expr._tag, "int")
        self.assertEqual(expr.value, -3)

    def test_parse_symbol(self):
        expr, rest = parse(["add"])
        self.assertEqual(rest, [])
        self.assertEqual(expr._tag, "symbol")
        self.assertEqual(expr.value, "add")

    def test_parse_list_def(self):
        expr, rest = parse(tokenize("(7 x def)"))
        self.assertEqual(rest, [])
        self.assertEqual(expr._tag, "link")
        # Link(Int(7), Link(Symbol("x"), Link(Symbol("def"), NIL)))
        self.assertEqual(expr._head._tag, "int")
        self.assertEqual(expr._tail._tag, "link")
        self.assertEqual(expr._tail._head._tag, "symbol")
        self.assertEqual(expr._tail._head.value, "x")
        self.assertEqual(expr._tail._tail._tag, "link")
        self.assertEqual(expr._tail._tail._head._tag, "symbol")
        self.assertEqual(expr._tail._tail._head.value, "def")
        self.assertEqual(expr._tail._tail._tail, NIL)

    def test_parse_err_form_is_plain_list(self):
        expr, rest = parse(tokenize("(arithmetic_error err)"))
        self.assertEqual(rest, [])
        self.assertEqual(expr._tag, "link")
        # Link(Symbol("arithmetic_error"), Link(Symbol("err"), NIL))
        self.assertEqual(expr._head._tag, "symbol")
        self.assertEqual(expr._head.value, "arithmetic_error")
        self.assertEqual(expr._tail._tag, "link")
        self.assertEqual(expr._tail._head._tag, "symbol")
        self.assertEqual(expr._tail._head.value, "err")
        self.assertEqual(expr._tail._tail, NIL)
        self.assertFalse(_is_error(expr))

    def test_parse_err_form_with_origin_is_plain_list(self):
        expr, rest = parse(tokenize("((7 0 div) arithmetic_error err)"))
        self.assertEqual(rest, [])
        self.assertEqual(expr._tag, "link")
        # Link(Link(7, Link(0, Link(div, NIL))), Link(Symbol("arithmetic_error"), Link(Symbol("err"), NIL)))
        self.assertEqual(expr._head._tag, "link")  # inner (7 0 div)
        self.assertEqual(expr._tail._tag, "link")
        self.assertEqual(expr._tail._head._tag, "symbol")
        self.assertEqual(expr._tail._head.value, "arithmetic_error")
        self.assertEqual(expr._tail._tail._tag, "link")
        self.assertEqual(expr._tail._tail._head._tag, "symbol")
        self.assertEqual(expr._tail._tail._head.value, "err")
        self.assertEqual(expr._tail._tail._tail, NIL)
        self.assertFalse(_is_error(expr))

    def test_parse_float(self):
        expr, rest = parse(["3.14"])
        self.assertEqual(rest, [])
        self.assertEqual(expr._tag, "fp64")
        self.assertAlmostEqual(expr._value, 3.14)

    def test_parse_hex_bytes(self):
        expr, rest = parse(["0x1f"])
        self.assertEqual(rest, [])
        self.assertEqual(expr._tag, "bytes")
        self.assertEqual(expr.value, b"\x1f")

    def test_parse_string(self):
        expr, rest = parse(['"hello"'])
        self.assertEqual(rest, [])
        self.assertEqual(expr._tag, "str")
        self.assertEqual(expr.value, "hello")

    def test_parse_returns_rest(self):
        expr, rest = parse(tokenize("7 8"))
        self.assertEqual(expr._tag, "int")
        self.assertEqual(expr.value, 7)
        self.assertEqual(rest, ["8"])

    # ---- quote parsing ----

    def test_parse_quote_postfix(self):
        """((7 3) ') — postfix quote: ' is the tail, inner list is the expression."""
        expr, rest = parse(tokenize("((7 3) ')"))
        self.assertEqual(rest, [])
        self.assertEqual(expr._tag, "link")
        # Link(Link(7, Link(3, NIL)), Link(Symbol("'"), NIL))
        self.assertEqual(expr._head._tag, "link")  # inner (7 3)
        self.assertEqual(expr._head._head._tag, "int")
        self.assertEqual(expr._head._tail._tag, "link")
        self.assertEqual(expr._head._tail._head._tag, "int")
        self.assertEqual(expr._head._tail._tail, NIL)
        self.assertEqual(expr._tail._tag, "link")
        self.assertEqual(expr._tail._head._tag, "symbol")
        self.assertEqual(expr._tail._head.value, "'")
        self.assertEqual(expr._tail._tail, NIL)

    def test_parse_quote_symbol_inside_list(self):
        """(7 3 ') — ' inside a list is just a regular symbol, not wrapping."""
        expr, rest = parse(tokenize("(7 3 ')"))
        self.assertEqual(rest, [])
        self.assertEqual(expr._tag, "link")
        # Link(Int(7), Link(Int(3), Link(Symbol("'"), NIL)))
        self.assertEqual(expr._head._tag, "int")
        self.assertEqual(expr._tail._tag, "link")
        self.assertEqual(expr._tail._head._tag, "int")
        self.assertEqual(expr._tail._tail._tag, "link")
        self.assertEqual(expr._tail._tail._head._tag, "symbol")
        self.assertEqual(expr._tail._tail._head.value, "'")
        self.assertEqual(expr._tail._tail._tail, NIL)

    def test_parse_quote_symbol_at_toplevel(self):
        """' at top level is just a regular Symbol('\")."""
        expr, rest = parse(tokenize("'"))
        self.assertEqual(expr._tag, "symbol")
        self.assertEqual(expr.value, "'")

    def test_parse_quote_keyword_is_symbol(self):
        """The token 'quote' is a plain Symbol('quote')."""
        expr, rest = parse(tokenize("quote"))
        self.assertEqual(expr._tag, "symbol")
        self.assertEqual(expr.value, "quote")


if __name__ == "__main__":
    unittest.main()
