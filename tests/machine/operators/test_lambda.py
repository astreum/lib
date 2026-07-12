import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine
from astreum.expression import NIL


def _is_tagged(expr, tag):
    return (
        expr._tag == "link"
        and expr._tail is not None
        and expr._tail._tag == "symbol"
        and expr._tail.value == tag
    )


class TestLambdaOperator(unittest.TestCase):
    """lambda & apply — tagged function values."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- lambda creates tagged link pair ---

    def test_lambda_creates_tagged_value(self):
        """('(a) '(a 1 +) lambda) pushes tagged link pair with 'lambda tag."""
        expr, _ = parse(tokenize("('(a) '(a 1 +) lambda)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "lambda"))

    # --- apply invokes lambda value ---

    def test_apply_invokes_lambda(self):
        """(42 '(a) '(a 1 +) lambda apply) -> 43."""
        expr, _ = parse(tokenize("(42 '(a) '(a 1 +) lambda apply)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 43)

    def test_apply_multiple_args(self):
        """(3 5 '(a b) '(a b +) lambda apply) -> 8."""
        expr, _ = parse(tokenize("(3 5 '(a b) '(a b +) lambda apply)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 8)

    # --- lambda value via def ---

    def test_lambda_via_def(self):
        """'(a b) '(a b +) lambda 'add def then 3 5 add apply -> 8."""
        expr, _ = parse(tokenize("('(a b) '(a b +) lambda 'add def 3 5 add apply)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 8)

    # --- env capture ---

    def test_lambda_captures_env(self):
        """Outer 10 'x def, push 5, create lambda, then apply -> 15."""
        expr, _ = parse(tokenize("(10 'x def 5 '(a) '(a x +) lambda apply)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 15)

    # --- tagged fn value via manual link ---

    def test_apply_tagged_fn(self):
        """(3 5 '(a b +) '(a b) link 'fn link apply) -> 8."""
        expr, _ = parse(tokenize("(3 5 '(a b +) '(a b) link 'fn link apply)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 8)

    def test_apply_tagged_fn_live_env(self):
        """fn-tagged value sees parent env at apply time."""
        expr, _ = parse(tokenize("(10 'x def 5 '(a x +) '(a) link 'fn link apply)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 15)

    def test_apply_tagged_box(self):
        """box-tagged value has parent=None (isolated); x is unbound -> NIL."""
        expr, _ = parse(tokenize("(10 'x def 5 '(a x +) '(a) link 'box link apply)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    # --- errors ---

    def test_apply_non_function(self):
        """(42 apply) -> OpError("apply of int")."""
        expr, _ = parse(tokenize("(42 apply)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    def test_apply_underflow(self):
        """(apply) -> OpError("stack underflow")."""
        expr, _ = parse(tokenize("(apply)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    def test_apply_arg_underflow(self):
        """('(a) '(a 1 +) lambda apply) -> OpError("stack underflow")."""
        expr, _ = parse(tokenize("('(a) '(a 1 +) lambda apply)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    def test_apply_extra_args(self):
        """(7 3 5 '(a b) '(a b +) lambda apply) -> 8 (7 stays on stack)."""
        expr, _ = parse(tokenize("(7 3 5 '(a b) '(a b +) lambda apply)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 8)

    def test_lambda_non_link_params(self):
        """(42 '(a 1 +) lambda) -> OpError("lambda of int")."""
        expr, _ = parse(tokenize("(42 '(a 1 +) lambda)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    def test_lambda_underflow(self):
        """(lambda) -> OpError("stack underflow")."""
        expr, _ = parse(tokenize("(lambda)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    def test_lambda_missing_body(self):
        """('(a) lambda) -> OpError("stack underflow")."""
        expr, _ = parse(tokenize("('(a) lambda)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    # --- deterministic mode ---

    def test_lambda_deterministic(self):
        """lambda creates a tagged link pair in deterministic mode."""
        expr, _ = parse(tokenize("('(a) '(a 1 +) lambda)"))
        self.machine.mode = "deterministic"
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "lambda"))

    def test_apply_deterministic(self):
        """apply invokes lambda in deterministic mode."""
        expr, _ = parse(tokenize("(42 '(a) '(a 1 +) lambda apply)"))
        self.machine.mode = "deterministic"
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result._value, 43)

    # --- tagged forms (with_result) ---

    def test_lambda_tagged_ok(self):
        """('(a) '(a 1 +) lambda?) -> (tagged-link-pair . ok)."""
        expr, _ = parse(tokenize("('(a) '(a 1 +) lambda?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertTrue(_is_tagged(result._head, "lambda"))

    def test_lambda_tagged_err(self):
        """(lambda?) -> ("stack underflow" . err)."""
        expr, _ = parse(tokenize("(lambda?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "stack underflow")

    def test_apply_tagged_ok(self):
        """(42 '(a) '(a 1 +) lambda apply?) -> (43 . ok)."""
        expr, _ = parse(tokenize("(42 '(a) '(a 1 +) lambda apply?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "int")
        self.assertEqual(result._head.value, 43)

    def test_apply_tagged_err(self):
        """(apply?) -> ("stack underflow" . err)."""
        expr, _ = parse(tokenize("(apply?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "stack underflow")

    # --- function value properties ---

    def test_lambda_value_type(self):
        """type returns symbol("lambda") for tagged lambda."""
        expr, _ = parse(tokenize("('(a) '(a 1 +) lambda type)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "symbol")
        self.assertEqual(result.value, "lambda")

    def test_lambda_value_hash_not_operator(self):
        """hash is not an operator; returns (None . None)."""
        expr, _ = parse(tokenize("('(a) '(a 1 +) lambda hash)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_lambda_value_bytes_not_supported(self):
        """bytes operator does not handle link tag."""
        expr, _ = parse(tokenize("('(a) '(a 1 +) lambda bytes)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    # --- nested apply with manual fn tag ---

    def test_nested_apply(self):
        """Manual fn-tagged value inside lambda -> 26."""
        expr, _ = parse(tokenize(
            "(5 '(a) '(20 '(b 1 +) '(b) link 'fn link apply a +) lambda apply)"
        ))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 26)


if __name__ == "__main__":
    unittest.main(verbosity=2)
