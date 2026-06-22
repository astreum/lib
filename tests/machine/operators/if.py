import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine
from astreum.machine.models.expression import NIL
from astreum.machine.evaluation.operators._if import is_truthy


def _is_tagged(expr, tag):
    return (
        isinstance(expr, Expr.Link)
        and isinstance(expr.head, Expr.Symbol)
        and expr.head.value == tag
    )


class TestIsTruthy(unittest.TestCase):
    """Direct unit tests for is_truthy (no parse/evaluate)."""

    def test_int_zero_falsy(self):
        self.assertFalse(is_truthy(Expr.Int(0)))

    def test_int_nonzero_truthy(self):
        self.assertTrue(is_truthy(Expr.Int(42)))

    def test_float_zero_falsy(self):
        self.assertFalse(is_truthy(Expr.Float(0.0)))
        self.assertFalse(is_truthy(Expr.Float(-0.0)))

    def test_float_nonzero_truthy(self):
        self.assertTrue(is_truthy(Expr.Float(1.5)))

    def test_bytes_empty_falsy(self):
        self.assertFalse(is_truthy(Expr.Bytes(b"")))

    def test_bytes_nonempty_truthy(self):
        self.assertTrue(is_truthy(Expr.Bytes(b"\x01")))

    def test_nil_falsy(self):
        self.assertFalse(is_truthy(NIL))

    def test_ok_truthy(self):
        ok_val = Expr.Link(Expr.Symbol("ok"), Expr.Int(42))
        self.assertTrue(is_truthy(ok_val))
        ok_nil = Expr.Link(Expr.Symbol("ok"), NIL)
        self.assertTrue(is_truthy(ok_nil))

    def test_err_falsy(self):
        err_val = Expr.Link(Expr.Symbol("err"), Expr.String("x"))
        self.assertFalse(is_truthy(err_val))

    def test_symbol_truthy(self):
        self.assertTrue(is_truthy(Expr.Symbol("foo")))

    def test_string_truthy(self):
        self.assertTrue(is_truthy(Expr.String("hello")))

    def test_link_plain_truthy(self):
        link_val = Expr.Link(Expr.Int(42), NIL)
        self.assertTrue(is_truthy(link_val))


class TestIfOperator(unittest.TestCase):
    """if — conditional, bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare success ---

    def test_bare_int_truthy(self):
        """(1 99 42 if) -> Int(99)."""
        expr, _ = parse(tokenize("(1 99 42 if)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 99)

    def test_bare_int_falsy(self):
        """(0 99 42 if) -> Int(42)."""
        expr, _ = parse(tokenize("(0 99 42 if)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 42)

    def test_bare_float_truthy(self):
        """(1.5 99 42 if) -> Int(99)."""
        expr, _ = parse(tokenize("(1.5 99 42 if)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 99)

    def test_bare_float_falsy(self):
        """(0.0 99 42 if) -> Int(42)."""
        expr, _ = parse(tokenize("(0.0 99 42 if)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 42)

    def test_bare_bytes_truthy(self):
        """(0x01 99 42 if) -> Int(99)."""
        expr, _ = parse(tokenize("(0x01 99 42 if)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 99)

    def test_bare_bytes_falsy(self):
        """(0x 99 42 if) -> Int(42)."""
        expr, _ = parse(tokenize("(0x 99 42 if)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 42)

    def test_bare_nil_falsy(self):
        """('x 99 42 if) -> Int(42) (unbound -> NIL -> falsy)."""
        expr, _ = parse(tokenize("('x 99 42 if)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 42)

    # --- bare errors -> NIL ---

    def test_bare_underflow(self):
        """(if) -> NIL."""
        expr, _ = parse(tokenize("(if)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    # --- tagged success ---

    def test_tagged_int_truthy(self):
        """(1 99 42 if?) -> (ok Int(99))."""
        expr, _ = parse(tokenize("(1 99 42 if?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Int)
        self.assertEqual(result.tail.value, 99)

    def test_tagged_int_falsy(self):
        """(0 99 42 if?) -> (ok Int(42))."""
        expr, _ = parse(tokenize("(0 99 42 if?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Int)
        self.assertEqual(result.tail.value, 42)

    # --- tagged errors -> (err ...) ---

    def test_tagged_underflow(self):
        """(if?) -> (err "stack underflow")."""
        expr, _ = parse(tokenize("(if?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
