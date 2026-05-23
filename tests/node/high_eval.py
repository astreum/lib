import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Meter, Expr  # noqa: E402
from astreum.machine.tokenizer import tokenize  # noqa: E402
from astreum.machine.parser import parse  # noqa: E402
from astreum.node import Node  # noqa: E402


class TestHighEvalFeatures(unittest.TestCase):
    def setUp(self):
        self.node = Node()

    # ---- def with environment ----

    def test_def_no_parent_env(self):
        """(7 seven def) with env_id=None — parent_id is None, should error."""
        expr, _ = parse(tokenize("(7 seven def)"))
        result = self.node.high_eval(expr=expr, env_id=None, meter=Meter())
        self.assertIsInstance(result, Expr.ListExpr)
        self.assertIsInstance(result.elements[0], Expr.Symbol)
        self.assertEqual(result.elements[0].value, "error")

    def test_def_wrapped_outer_parens(self):
        """((7 seven def)) with env_id=None — outer parens create an env, no error."""
        expr, _ = parse(tokenize("((7 seven def))"))
        result = self.node.high_eval(expr=expr, env_id=None, meter=Meter())
        self.assertIsInstance(result, Expr.Symbol)
        self.assertEqual(result.value, "seven")

    def test_def_then_lookup_resolves(self):
        """((7 seven def) seven) — default resolver runs left-to-right, def stores, lookup finds."""
        expr, _ = parse(tokenize("((7 seven def) seven)"))
        result = self.node.high_eval(expr=expr, env_id=None, meter=Meter())
        print(repr(result))
        self.assertIsInstance(result, Expr.ListExpr)
        self.assertEqual(len(result.elements), 2)
        self.assertIsInstance(result.elements[0], Expr.Symbol)
        self.assertEqual(result.elements[0].value, "seven")
        self.assertIsInstance(result.elements[1], Expr.Bytes)
        self.assertEqual(int.from_bytes(result.elements[1].value, "big"), 7)
        self.assertEqual(repr(result), "(seven 7)")

    def test_sub_define_then_call(self):
        """((body sub def) (7 3 sub sk)) — define sub body, then call it via sk."""
        expr, _ = parse(tokenize(
            "((($1 $1 nand 1 add $0 add) sub def) (7 3 sub sk))"
        ))
        result = self.node.high_eval(expr=expr, env_id=None, meter=Meter())
        print(repr(result))
        self.assertIsInstance(result, Expr.ListExpr)
        self.assertEqual(len(result.elements), 2)
        self.assertIsInstance(result.elements[0], Expr.Symbol)
        self.assertEqual(result.elements[0].value, "sub")
        self.assertIsInstance(result.elements[1], Expr.Bytes)
        self.assertEqual(int.from_bytes(result.elements[1].value, "big"), 4)
        self.assertEqual(repr(result), "(sub 4)")

    def test_mul_define_then_call(self):
        """((mul_body mul def) (3 5 mul sk)) — define mul, then call it."""
        expr, _ = parse(tokenize(
            "(((a $0 heap_set b $1 heap_set r 0 heap_set "
            "32 1 jump "
            "r r heap_get a heap_get add heap_set "
            "b b heap_get 1 1 nand 1 add add heap_set "
            "32 1 jump "
            "e b heap_get heap_set "
            "12 e heap_get jump "
            "r heap_get) mul def) "
            "(3 5 mul sk))"
        ))
        result = self.node.high_eval(expr=expr, env_id=None, meter=Meter())
        print(repr(result))
        self.assertIsInstance(result, Expr.ListExpr)
        self.assertEqual(len(result.elements), 2)
        self.assertIsInstance(result.elements[1], Expr.Bytes)
        self.assertEqual(int.from_bytes(result.elements[1].value, "big"), 15)

    def test_sub_inline_quoted(self):
        """(7 3 (body ') sk) — quote returns body unevaluated, sk emits it."""
        expr, _ = parse(tokenize(
            "(7 3 (($1 $1 nand 1 add $0 add) ') sk)"
        ))
        result = self.node.high_eval(expr=expr, env_id=None, meter=Meter())
        print(repr(result))
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "big"), 4)

    # ---- factorial via if ----

    def test_fact_5(self):
        expr, _ = parse(tokenize(
            "((($1 $1 nand 1 add $0 add) sub def) "
            "((res 0 heap_set nb $1 $1 nand heap_set na $0 $0 nand heap_set "
            "rx $0 nb heap_get nand heap_set ry na heap_get $1 nand heap_set "
            "x rx heap_get ry heap_get nand heap_set 39 x heap_get jump "
            "res 1 heap_set res heap_get) eq def) "
            "((a $0 heap_set b $1 heap_set r 0 heap_set "
            "32 1 jump "
            "r r heap_get a heap_get add heap_set "
            "b b heap_get 1 1 nand 1 add add heap_set "
            "32 1 jump "
            "e b heap_get heap_set "
            "12 e heap_get jump "
            "r heap_get) mul def) "
            "(((m 1 eq sk) 1 (m ((m 1 sub sk) (m) fact fn) mul sk) if) fact def) "
            "(5 (m) fact fn))"
        ))
        result = self.node.high_eval(expr=expr, env_id=None, meter=Meter())
        print(repr(result))
        self.assertIsInstance(result, Expr.ListExpr)
        self.assertEqual(len(result.elements), 5)
        self.assertIsInstance(result.elements[4], Expr.Bytes)
        self.assertEqual(int.from_bytes(result.elements[4].value, "big"), 120)


if __name__ == "__main__":
    unittest.main()
