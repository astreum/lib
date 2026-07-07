import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


def _is_tagged(expr, tag):
    return (
        expr._tag == "link"
        and expr._tail is not None
        and expr._tail._tag == "symbol"
        and expr._tail.value == tag
    )


class TestTaggedResultsDispatch(unittest.TestCase):
    """? suffix dispatch: <primitive>? wraps result as (ok v) / (err reason)."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_bare_op_unchanged(self):
        """(7 8 +) -> 15 (no tuple)."""
        expr, _ = parse(tokenize("(7 8 +)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 15)

    def test_suffixed_op_success_returns_ok(self):
        """(7 8 +?) -> (ok . 15)."""
        expr, _ = parse(tokenize("(7 8 +?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "int")
        self.assertEqual(result._head.value, 15)

    def test_suffixed_op_underflow_returns_err_underflow(self):
        """(drop?) on empty -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("(drop?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "stack underflow")

    def test_suffixed_op_void_success_returns_ok_nil(self):
        """(1 drop?) -> (ok . NIL) (succeeded, empty stack)."""
        expr, _ = parse(tokenize("(1 drop?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "link")
        self.assertIsNone(result._head._head)
        self.assertIsNone(result._head._tail)

    def test_bare_underflow_returns_nil(self):
        """(drop) on empty -> NIL (caught by OpError handler)."""
        expr, _ = parse(tokenize("(drop)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_suffixed_non_primitive_returns_unbound_nil(self):
        """(my-fn?) -> NIL (primitives only, stem not in OPERATOR_LIST)."""
        expr, _ = parse(tokenize("(my-fn?)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_deterministic_strips_suffix(self):
        """deterministic (7 8 +?) -> 15 (suffix stripped, no tuple)."""
        machine = Machine(node=None, mode="deterministic")
        expr, _ = parse(tokenize("(7 8 +?)"))
        result = machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 15)
        self.assertFalse(_is_tagged(result, "ok"))
        self.assertFalse(_is_tagged(result, "err"))

    def test_suffixed_swap_success(self):
        """(1 2 swap?) -> (ok . NIL) (void op)."""
        expr, _ = parse(tokenize("(1 2 swap?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "link")
        self.assertIsNone(result._head._head)
        self.assertIsNone(result._head._tail)

    def test_suffixed_swap_underflow(self):
        """(1 swap?) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("(1 swap?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "stack underflow")

    def test_op_error_message_becomes_reason(self):
        """(7 0 /?) -> (err . "division by zero") (OpError from real div op)."""
        expr, _ = parse(tokenize("(7 0 /?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "division by zero")

    def test_meter_exceeded_propagates(self):
        """MeterExceededError is not swallowed by ? wrapper."""
        machine = Machine(node=None, meter_limit=5)
        expr, _ = parse(tokenize("(999999999999999999999999 1 +?)"))
        from astreum.machine.models.meter import MeterExceededError
        with self.assertRaises(MeterExceededError):
            machine.run(expr=expr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
