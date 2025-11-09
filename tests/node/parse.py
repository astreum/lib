import unittest
import importlib.util
from pathlib import Path


# Load src/astreum/_node.py directly to access its parser
_node_path = Path(__file__).resolve().parents[2] / "src" / "astreum" / "_node.py"
_spec = importlib.util.spec_from_file_location("_astreum_low_node", str(_node_path))
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)

tokenize = getattr(_mod, "tokenize")
parse = getattr(_mod, "parse")
Expr = getattr(_mod, "Expr")


def _is_error(expr):
    return (
        isinstance(expr, Expr.ListExpr)
        and bool(expr.elements)
        and isinstance(expr.elements[0], Expr.Symbol)
        and expr.elements[0].value == "error"
    )


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


if __name__ == "__main__":
    unittest.main()
