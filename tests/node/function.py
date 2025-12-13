import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Env, Expr  # noqa: E402
from astreum.node import Node  # noqa: E402


class TestFunctionSubtract(unittest.TestCase):
    def setUp(self):
        self.node = Node()
        self.env_id = uuid.uuid4()
        self.node.environments[self.env_id] = Env()

    def test_define_subtract_fn_and_call(self):
        # Build a stack-level subtractor via sk inside a high-level fn:
        # body: ($1 $1 nand 1 add $0 add) => a + (~b + 1) = a - b
        low_body = Expr.ListExpr([
            Expr.Symbol("$1"),  # b
            Expr.Symbol("$1"),  # b
            Expr.Symbol("nand"),
            Expr.Bytes(b"\x01"),
            Expr.Symbol("add"),
            Expr.Symbol("$0"),  # a
            Expr.Symbol("add"),
        ])

        body_expr = Expr.ListExpr([
            Expr.Symbol("a"),
            Expr.Symbol("b"),
            Expr.ListExpr([low_body, Expr.Symbol("sk")]),
        ])
        params_expr = Expr.ListExpr([Expr.Symbol("a"), Expr.Symbol("b")])
        fn_value = Expr.ListExpr([body_expr, params_expr, Expr.Symbol("fn")])

        # Store function under 'int.sub' directly (current def evaluates value
        # and would resolve the 'fn' symbol prematurely in this implementation).
        self.node.env_set(self.env_id, "int.sub", fn_value)

        # Retrieve the function and use it as the tail of a call expression
        bound_fn = self.node.env_get(self.env_id, "int.sub")
        self.assertIsInstance(bound_fn, Expr.ListExpr)

        call_expr = Expr.ListExpr([Expr.Bytes(b"\x07"), Expr.Bytes(b"\x04"), bound_fn])
        result = self.node.high_eval(self.env_id, call_expr)

        self.assertIsInstance(result, Expr.ListExpr)
        self.assertEqual(len(result.elements), 1)
        self.assertIsInstance(result.elements[0], Expr.Bytes)
        # 7 - 4 == 3 => 0x03 in one byte
        self.assertEqual(int.from_bytes(result.elements[0].value, "big", signed=True), 3)


if __name__ == "__main__":
    unittest.main()
