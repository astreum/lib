import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine
from astreum.machine.models.expression import NIL, int_, float_, bytes_, str_, symbol, link


def _is_tagged(expr, tag):
    return (
        expr._tag == "link"
        and expr._head._tag == "symbol"
        and expr._head.value == tag
    )


class TestLambdaOperator(unittest.TestCase):
    """lambda — inline function application (no def_target), bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare success ---

    def test_bare_add(self):
        """(3 5 '(a b) '(a b +) lambda) -> Int(8)."""
        expr, _ = parse(tokenize("(3 5 '(a b) '(a b +) lambda)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 8)

    # --- bare errors -> NIL ---

    def test_bare_underflow(self):
        """(lambda) -> NIL."""
        expr, _ = parse(tokenize("(lambda)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    def test_bare_missing_params(self):
        """(42 lambda) -> NIL (params underflow)."""
        expr, _ = parse(tokenize("(42 lambda)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    def test_bare_wrong_params_type(self):
        """(42 42 lambda) -> NIL (lambda of int)."""
        expr, _ = parse(tokenize("(42 42 lambda)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    def test_bare_missing_args(self):
        """('(a b) '(a b +) lambda) -> NIL (args underflow)."""
        expr, _ = parse(tokenize("('(a b) '(a b +) lambda)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    # --- tagged success ---

    def test_tagged_add(self):
        """(3 5 '(a b) '(a b +) lambda?) -> (ok Int(8))."""
        expr, _ = parse(tokenize("(3 5 '(a b) '(a b +) lambda?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._tail._tag, "int")
        self.assertEqual(result._tail.value, 8)

    def test_tagged_pass_through_ok(self):
        """(3 5 '(a b) '(a b <? ) lambda?) -> (ok Bytes(\\x01)) (1 layer)."""
        expr, _ = parse(tokenize("(3 5 '(a b) '(a b <? ) lambda?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._tail._tag, "bytes")
        self.assertEqual(result._tail.value, b"\x01")

    def test_tagged_pass_through_err(self):
        """(3 "x" '(a b) '(a b +?) lambda?) -> (err "addition of int and str") (1 layer)."""
        expr, _ = parse(tokenize('(3 "x" \'(a b) \'(a b +?) lambda?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "addition of int and str")

    # --- tagged errors -> (err ...) ---

    def test_tagged_underflow(self):
        """(lambda?) -> (err "stack underflow")."""
        expr, _ = parse(tokenize("(lambda?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "stack underflow")

    def test_tagged_wrong_params_type(self):
        """(42 42 lambda?) -> (err "lambda of int")."""
        expr, _ = parse(tokenize("(42 42 lambda?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "lambda of int")

    def test_tagged_missing_args(self):
        """('(a b) '(a b +) lambda?) -> (err "stack underflow")."""
        expr, _ = parse(tokenize("('(a b) '(a b +) lambda?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "stack underflow")


    # --- scope: lambda has no parent env and no def_target ---

    def test_bare_cannot_read_outer_def(self):
        """((99 'outer_val def) (0 '(a) 'outer_val lambda)) -> NIL."""
        expr, _ = parse(tokenize("((99 'outer_val def) (0 '(a) 'outer_val lambda))"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_tagged_cannot_read_outer_def(self):
        """((99 'outer_val def) (0 '(a) 'outer_val lambda?)) -> (ok NIL)."""
        expr, _ = parse(tokenize("((99 'outer_val def) (0 '(a) 'outer_val lambda?))"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._tail._tag, "link")
        self.assertIsNone(result._tail._head)
        self.assertIsNone(result._tail._tail)

    def test_bare_def_inside_does_not_leak(self):
        """((5 'x def) (0 '(a) '((99 'x def) a) lambda) x) -> Int(5)."""
        expr, _ = parse(tokenize("((5 'x def) (0 '(a) '((99 'x def) a) lambda) x)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 5)

    def test_tagged_def_inside_does_not_leak(self):
        """((5 'x def) (0 '(a) '((99 'x def) a) lambda?) x) -> Int(5)."""
        expr, _ = parse(tokenize("((5 'x def) (0 '(a) '((99 'x def) a) lambda?) x)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
