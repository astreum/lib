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
        and expr._tail is not None
        and expr._tail._tag == "symbol"
        and expr._tail.value == tag
    )


class TestRecOperator(unittest.TestCase):
    """rec — recursive combinator, bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare success ---

    def test_bare_factorial(self):
        """(5 '(dup 0 is_eq) '(drop 1) '(dup 1 -) '(swap *) rec) -> Int(120)."""
        expr, _ = parse(tokenize("(5 '(dup 0 is_eq) '(drop 1) '(dup 1 -) '(swap *) rec)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 120)

    def test_bare_sum(self):
        """(5 '(dup 0 is_eq) '(drop 0) '(dup 1 -) '(+) rec) -> Int(15)."""
        expr, _ = parse(tokenize("(5 '(dup 0 is_eq) '(drop 0) '(dup 1 -) '(+) rec)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 15)

    # --- bare underflow -> NIL ---

    def test_bare_underflow(self):
        """(rec) -> NIL."""
        expr, _ = parse(tokenize("(rec)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    def test_bare_partial_underflow(self):
        """(1 2 rec) -> NIL."""
        expr, _ = parse(tokenize("(1 2 rec)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    # --- bare error propagation -> NIL ---

    def test_bare_error_in_pred(self):
        """Pred with ? error -> NIL."""
        expr, _ = parse(tokenize(
            '(5 \'(1 "x" +?) \'(drop 1) \'(dup 1 -) \'(swap *) rec)'
        ))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    def test_bare_error_in_rec1(self):
        """rec1 with ? error -> NIL."""
        expr, _ = parse(tokenize(
            '(5 \'(dup 0 is_eq) \'(drop 1) \'(1 "x" +?) \'(swap *) rec)'
        ))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    def test_bare_error_in_rec2(self):
        """rec2 with ? error -> NIL."""
        expr, _ = parse(tokenize(
            '(5 \'(dup 0 is_eq) \'(drop 1) \'(dup 1 -) \'(1 "x" +?) rec)'
        ))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    # --- tagged success -> (ok ...) ---

    def test_tagged_success(self):
        """rec? -> (ok Int(120))."""
        expr, _ = parse(tokenize("(5 '(dup 0 is_eq) '(drop 1) '(dup 1 -) '(swap *) rec?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "int")
        self.assertEqual(result._head.value, 120)

    # --- tagged underflow -> (err ...) ---

    def test_tagged_underflow(self):
        """(rec?) -> (err "stack underflow")."""
        expr, _ = parse(tokenize("(rec?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "stack underflow")

    # --- tagged error propagation -> (err ...) ---

    def test_tagged_error_in_pred(self):
        """rec? with error in pred -> (err ...)."""
        expr, _ = parse(tokenize(
            '(5 \'(1 "x" +?) \'(drop 1) \'(dup 1 -) \'(swap *) rec?)'
        ))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "addition of int and str")

    def test_tagged_error_in_rec1(self):
        """rec? with error in rec1 -> (err ...)."""
        expr, _ = parse(tokenize(
            '(5 \'(dup 0 is_eq) \'(drop 1) \'(1 "x" +?) \'(swap *) rec?)'
        ))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "addition of int and str")

    def test_tagged_error_in_rec2(self):
        """rec? with error in rec2 -> (err ...)."""
        expr, _ = parse(tokenize(
            '(5 \'(dup 0 is_eq) \'(drop 1) \'(dup 1 -) \'(1 "x" +?) rec?)'
        ))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "addition of int and str")


if __name__ == "__main__":
    unittest.main(verbosity=2)
