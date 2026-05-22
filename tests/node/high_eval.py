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

    # ---- sub via def + named dispatch ----

    def test_sub_named_7_minus_3(self):
        expr, _ = parse(tokenize("(($1 $1 nand 1 add $0 add) sub def)"))
        self.node.high_eval(None, expr, Meter(limit=1024))
        expr, _ = parse(tokenize("(7 3 sub)"))
        result = self.node.high_eval(None, expr, Meter(limit=1024))
        self.assertEqual(result.value, 4)

    def test_sub_named_10_minus_6(self):
        expr, _ = parse(tokenize("(($1 $1 nand 1 add $0 add) sub def)"))
        self.node.high_eval(None, expr, Meter(limit=1024))
        expr, _ = parse(tokenize("(10 6 sub)"))
        result = self.node.high_eval(None, expr, Meter(limit=1024))
        self.assertEqual(result.value, 4)

    # ---- inline sk still works ----

    def test_sub_inline_7_minus_3(self):
        expr, _ = parse(tokenize("(7 3 (($1 $1 nand 1 add $0 add) sk))"))
        result = self.node.high_eval(None, expr, Meter(limit=1024))
        self.assertEqual(result.value, 4)

    # ---- quote ----

    def test_quote_returns_unevaluated(self):
        expr, _ = parse(tokenize("'(7 3 sub)"))
        result = self.node.high_eval(None, expr, Meter(limit=1024))
        self.assertIsInstance(result, Expr.ListExpr)
        self.assertEqual(len(result.elements), 3)

    def test_quote_shorthand_equivalent(self):
        expr1, _ = parse(tokenize("'(7 3)"))
        expr2, _ = parse(tokenize("(7 3 ')"))
        result1 = self.node.high_eval(None, expr1, Meter(limit=1024))
        result2 = self.node.high_eval(None, expr2, Meter(limit=1024))
        self.assertEqual(len(result1.elements), len(result2.elements))

    # ---- eval ----

    def test_eval_quoted_expression(self):
        expr, _ = parse(tokenize("'(7 3 (($1 $1 nand 1 add $0 add) sk))"))
        quoted = self.node.high_eval(None, expr, Meter(limit=1024))
        self.assertIsInstance(quoted, Expr.ListExpr)
        # now eval it
        from astreum.machine.expression import Expr as ExprCls
        eval_expr = ExprCls.ListExpr([quoted, ExprCls.Symbol("eval")])
        result = self.node.high_eval(None, eval_expr, Meter(limit=1024))
        self.assertEqual(result.value, 4)

    # ---- if ----

    def test_if_true_branch(self):
        # (1 1 eq) is true → then=10
        expr, _ = parse(tokenize("((1 1 eq) 10 20 if)"))
        result = self.node.high_eval(None, expr, Meter(limit=1024))
        self.assertEqual(result.value, 10)

    def test_if_false_branch(self):
        # (1 0 eq) is false → else=20
        expr, _ = parse(tokenize("((1 0 eq) 10 20 if)"))
        result = self.node.high_eval(None, expr, Meter(limit=1024))
        self.assertEqual(result.value, 20)

    # ---- factorial via if ----

    def test_fact_5(self):
        # define sub, eq, mul, fact
        self.node.high_eval(None, parse(tokenize(
            "(($1 $1 nand 1 add $0 add) sub def)"
        ))[0], Meter(limit=1024))
        self.node.high_eval(None, parse(tokenize(
            "(0 res heap_set $1 $1 nand nb heap_set $0 $0 nand na heap_set "
            "$0 nb heap_get nand rx heap_set na heap_get $1 nand ry heap_set "
            "rx heap_get ry heap_get nand x heap_set 39 x heap_get jump "
            "1 res heap_set res heap_get) eq def"
        ))[0], Meter(limit=1024))
        self.node.high_eval(None, parse(tokenize(
            "(a $0 heap_set b $1 heap_set 0 r heap_set "
            "b heap_get b heap_get nand 255 nand e heap_set "
            "e heap_get e heap_get nand 45 jump "
            "r heap_get a heap_get add r heap_set "
            "b heap_get 1 1 nand 1 add add b heap_set "
            "9 1 jump r heap_get) mul def"
        ))[0], Meter(limit=4096))
        self.node.high_eval(None, parse(tokenize(
            "(((n 1 eq) (1) (n (n 1 sub fact) mul) if) (n) fn fact def)"
        ))[0], Meter(limit=4096))
        expr, _ = parse(tokenize("(5 fact)"))
        result = self.node.high_eval(None, expr, Meter(limit=8192))
        self.assertEqual(result.value, 120)


if __name__ == "__main__":
    unittest.main()
