import unittest
from src.astreum.node import Node, Expr
from src.astreum.lispeum import tokenize, parse


class TestNodeMachine(unittest.TestCase):
    """Integration tests for the Lispeum VM embedded in astreum.Node."""

    def setUp(self):
        # Spin‑up a stand‑alone VM
        self.node = Node({"machine-only": True})
        self.env_id = self.node.machine_create_environment()
        self.env = self.node.environments[self.env_id]

    # ---------- helpers --------------------------------------------------
    def _eval(self, source: str) -> Expr:
        """Tokenize → parse → eval a Lispeum snippet inside the current env."""
        tokens = tokenize(source)
        expr, _ = parse(tokens)
        return self.node.machine_expr_eval(env_id=self.env_id, expr=expr)

    # ---------- core tests ----------------------------------------------
    def test_int_addition(self):
        """(+ 2 3) ⇒ 5"""
        result = self._eval("(+ 2 3)")
        self.assertEqual(result.value, 5)

    def test_variable_definition_and_lookup(self):
        """(def numero 42) then numero ⇒ 42"""
        self._eval("(def numero 42)")
        lookup_result = self._eval("numero")
        self.assertEqual(lookup_result.value, 42)

    def test_session_isolation(self):
        """Variables defined in one session must not leak into another."""
        # Define in first env
        self._eval("(def a 1)")

        # Create second session
        other_env = self.node.machine_create_environment()

        tokens = tokenize("a")
        expr, _ = parse(tokens)
        result_other = self.node.machine_expr_eval(env_id=other_env, expr=expr)

        # Expect an Expr.Error or any non‑1 value
        self.assertTrue(
            isinstance(result_other, Expr.Error) or getattr(result_other, "value", None) != 1,
            "Variable 'a' leaked across sessions"
        )

        self.node.machine_delete_environment(other_env)


if __name__ == "__main__":
    unittest.main()
