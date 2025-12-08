import unittest
import uuid
import importlib.util
from pathlib import Path

# Load src/astreum/_node.py directly to avoid package-level circular imports
_node_path = Path(__file__).resolve().parents[2] / "src" / "astreum" / "_node.py"
_spec = importlib.util.spec_from_file_location("_astreum_low_node", str(_node_path))
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)

Node = getattr(_mod, "Node")
Env = getattr(_mod, "Env")
Expr = getattr(_mod, "Expr")


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
            Expr.Byte(1),
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

        call_expr = Expr.ListExpr([Expr.Byte(7), Expr.Byte(4), bound_fn])
        result = self.node.high_eval(self.env_id, call_expr)

        self.assertIsInstance(result, Expr.ListExpr)
        self.assertEqual(len(result.elements), 1)
        self.assertIsInstance(result.elements[0], Expr.Byte)
        # 7 - 4 == 3 => 0x03 in one byte
        self.assertEqual(result.elements[0].value & 0xFF, 0x03)


if __name__ == "__main__":
    unittest.main()
