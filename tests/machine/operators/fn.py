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


class TestFnOperator(unittest.TestCase):
    """fn — inline function application, bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare success ---

    def test_bare_add(self):
        """(3 5 '(a b) '(a b +) fn) -> Int(8)."""
        expr, _ = parse(tokenize("(3 5 '(a b) '(a b +) fn)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 8)

    # --- bare errors -> NIL ---

    def test_bare_underflow(self):
        """(fn) -> NIL."""
        expr, _ = parse(tokenize("(fn)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    def test_bare_missing_params(self):
        """(42 fn) -> NIL (params underflow)."""
        expr, _ = parse(tokenize("(42 fn)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    def test_bare_wrong_params_type(self):
        """(42 42 fn) -> NIL (fn of int)."""
        expr, _ = parse(tokenize("(42 42 fn)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    def test_bare_missing_args(self):
        """('(a b) '(a b +) fn) -> NIL (args underflow)."""
        expr, _ = parse(tokenize("('(a b) '(a b +) fn)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    # --- tagged success ---

    def test_tagged_add(self):
        """(3 5 '(a b) '(a b +) fn?) -> (ok Int(8))."""
        expr, _ = parse(tokenize("(3 5 '(a b) '(a b +) fn?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._tail._tag, "int")
        self.assertEqual(result._tail.value, 8)

    def test_tagged_pass_through_ok(self):
        """(3 5 '(a b) '(a b <? ) fn?) -> (ok Bytes(\\x01)) (1 layer)."""
        expr, _ = parse(tokenize("(3 5 '(a b) '(a b <? ) fn?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._tail._tag, "bytes")
        self.assertEqual(result._tail.value, b"\x01")

    def test_tagged_pass_through_err(self):
        """(3 "x" '(a b) '(a b +?) fn?) -> (err "addition of int and str") (1 layer)."""
        expr, _ = parse(tokenize('(3 "x" \'(a b) \'(a b +?) fn?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "addition of int and str")

    # --- tagged errors -> (err ...) ---

    def test_tagged_underflow(self):
        """(fn?) -> (err "stack underflow")."""
        expr, _ = parse(tokenize("(fn?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "stack underflow")

    def test_tagged_wrong_params_type(self):
        """(42 42 fn?) -> (err "fn of int")."""
        expr, _ = parse(tokenize("(42 42 fn?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "fn of int")

    def test_tagged_missing_args(self):
        """('(a b) '(a b +) fn?) -> (err "stack underflow")."""
        expr, _ = parse(tokenize("('(a b) '(a b +) fn?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "stack underflow")


    # --- scope: encloses defs via parent env and def_target ---

    def test_bare_reads_enclosing_def(self):
        """((99 'outer_val def) (0 '(a) 'outer_val fn)) -> Int(99)."""
        expr, _ = parse(tokenize("((99 'outer_val def) (0 '(a) 'outer_val fn))"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 99)

    def test_tagged_reads_enclosing_def(self):
        """((99 'outer_val def) (0 '(a) 'outer_val fn?)) -> (ok Int(99))."""
        expr, _ = parse(tokenize("((99 'outer_val def) (0 '(a) 'outer_val fn?))"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._tail._tag, "int")
        self.assertEqual(result._tail.value, 99)

    def test_bare_writes_def_outside(self):
        """((0 '(a) '((42 'y def) a) fn) y) -> Int(42)."""
        expr, _ = parse(tokenize("((0 '(a) '((42 'y def) a) fn) y)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 42)

    def test_tagged_writes_def_outside(self):
        """((0 '(a) '((42 'y def) a) fn?) y) -> Int(42)."""
        expr, _ = parse(tokenize("((0 '(a) '((42 'y def) a) fn?) y)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 42)


if __name__ == "__main__":
    unittest.main(verbosity=2)
