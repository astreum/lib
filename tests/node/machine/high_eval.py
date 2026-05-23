import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Meter, Expr  # noqa: E402
from astreum.machine.tokenizer import tokenize  # noqa: E402
from astreum.machine.parser import parse  # noqa: E402
from astreum.node import Node  # noqa: E402


class TestHighEval(unittest.TestCase):
    def setUp(self):
        self.node = Node()

    def test_mul_define_then_call(self):
        """((mul_body mul def) (2 3 mul sk)) — 2 * 3 = 6 by repeated addition."""
        expr, _ = parse(tokenize(
            # ---- init: a = $0, b = $1, r = 0 ----
            "(((a $0 heap_set b $1 heap_set r 0 heap_set "
            # ---- skip to exit check ----
            "32 1 jump "
            # ---- loop body (offset 12): r += a, b -= 1, back to check ----
            "r r heap_get a heap_get add heap_set "       # r = r + a
            "b b heap_get 1 1 nand 1 add add heap_set "   # b = b - 1
            "32 1 jump "
            # ---- exit check (offset 32): if b != 0, loop again ----
            "e b heap_get heap_set "                       # e = b
            "12 e heap_get jump "                          # if e != 0, jump to 12
            # ---- return r ----
            "r heap_get) mul def) "
            # ---- call mul(2, 3) via sk ----
            "(2 3 mul sk))"
        ))
        result = self.node.high_eval(expr=expr, env_id=None, meter=Meter())
        print(repr(result))
        self.assertIsInstance(result, Expr.ListExpr)
        self.assertEqual(len(result.elements), 2)
        self.assertIsInstance(result.elements[1], Expr.Bytes)
        self.assertEqual(int.from_bytes(result.elements[1].value, "big"), 6)


if __name__ == "__main__":
    unittest.main()
