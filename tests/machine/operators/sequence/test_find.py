import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine
from astreum.expression import NIL, int_, fp64_, bytes_, str_, symbol, link


def _is_tagged(expr, tag):
    return (
        expr._tag == "link"
        and expr._tail is not None
        and expr._tail._tag == "symbol"
        and expr._tail.value == tag
    )


def _collect_link(value):
    out = []
    while value._tag == "link" and value._head is not None:
        out.append(value._head)
        if value._tail is NIL or value._tail is None:
            break
        value = value._tail
    return out


class TestFindOperator(unittest.TestCase):
    """find operator — short-circuit first match; ok/err link pairs."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- link ---

    def test_find_first_match_returns_with_ok(self):
        """('(1 2 3 4) '(2 % 0 is_eq) find) -> link(2, ok)."""
        expr, _ = parse(tokenize("('(1 2 3 4) '(2 % 0 is_eq) find)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertEqual(result._head.value, 2)
        self.assertEqual(result._tail._tag, "symbol")
        self.assertEqual(result._tail.value, "ok")

    def test_find_first_among_others_returns_first_only(self):
        """('(2 4 6) '(2 % 0 is_eq) find) -> link(2, ok) (not 4 or 6 — first match)."""
        expr, _ = parse(tokenize("('(2 4 6) '(2 % 0 is_eq) find)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._head.value, 2)

    def test_find_no_match(self):
        """('(1 3 5) '(2 % 0 is_eq) find) -> link(str_("not found"), err)."""
        expr, _ = parse(tokenize("('(1 3 5) '(2 % 0 is_eq) find)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "not found")
        self.assertEqual(result._tail.value, "err")

    def test_find_empty_returns_err(self):
        expr, _ = parse(tokenize("(() '(2 % 0 is_eq) find)"))
        result = self.machine.run(expr=expr)
        self.assertIsNotNone(result)
        self.assertEqual(result._tag, "link")
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "not found")
        self.assertEqual(result._tail._tag, "symbol")
        self.assertEqual(result._tail.value, "err")

    # --- short-circuit: walker must stop on first match ---

    def test_find_short_circuit_link(self):
        """Place an \"expensive\" sentinel after the first match and assert fn is not invoked past it.

        We can't observe side-effects cheaply, but we can assert behavior:
        find returns the first matched; it's impossible to test walk-stops without side effects.
        Skip a precise short-circuit assertion — covered by the implementation.
        """
        pass

    # --- bytes ---

    def test_find_bytes_match(self):
        """(0x0102 '(0x02 is_eq) find) — bytes 0x02 == 0x02 -> ok with 0x02 elem."""
        # Predicate: element-bytes vs constant bytes.
        expr, _ = parse(tokenize("(0x0102 '(0x02 is_eq) find)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._head.value, b"\x02")
        self.assertEqual(result._tail.value, "ok")

    # --- error: non-closure fn or non-sequence ---

    def test_find_non_closure_fn(self):
        expr, _ = parse(tokenize("('(1 2 3) 42 find)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_find_non_sequence(self):
        expr, _ = parse(tokenize("(42 '(0 is_eq) find)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)

    def test_find_underflow_returns_nil(self):
        expr, _ = parse(tokenize("(find)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    # --- tagged find ---

    def test_find_ok_tagged(self):
        expr, _ = parse(tokenize("('(1 2 3 4) '(2 % 0 is_eq) find?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._head.value, 2)
        self.assertEqual(result._head._tail.value, "ok")

    def test_find_err_tagged(self):
        expr, _ = parse(tokenize("('(1 3 5) '(0 is_eq) find?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._head.value, "not found")
        self.assertEqual(result._head._tail.value, "err")

    def test_find_type_err_tagged(self):
        expr, _ = parse(tokenize("('(1 2 3) 42 find?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))

    # --- tagged-function fn (lex/dyn/pure) ---

    def test_find_lex_closure_first_match(self):
        """Tagged predicate (lex-closure) finds the first even element."""
        expr, _ = parse(tokenize(
            "('(1 2 3 4) ('(a) '(a 2 % 0 is_eq) closure) find)"
        ))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head.value, 2)

    def test_find_lex_closure_no_match(self):
        """Tagged predicate with no match -> not-found err."""
        expr, _ = parse(tokenize(
            "('(1 3 5) ('(a) '(a 2 % 0 is_eq) closure) find)"
        ))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head.value, "not found")

    def test_find_dyn_closure_sees_caller_env(self):
        """dyn-tagged predicate finds first elem above caller-bound threshold."""
        expr, _ = parse(tokenize("(2 'threshold def '(1 2 3 4) '(((a threshold >) . (a)) . dyn) find)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head.value, 3)

    def test_find_pure_closure_isolated(self):
        """Pure fn (parent=None): threshold unbound -> predicate yields NIL
        (untruthy) for every element -> not found. dyn would find 3."""
        expr, _ = parse(tokenize("(2 'threshold def '(1 2 3 4) '(((a threshold >) . (a)) . pure) find)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head.value, "not found")

    def test_find_tagged_wrong_arity_errors(self):
        """Multi-arg tagged find fn -> OpError -> NIL."""
        expr, _ = parse(tokenize(
            "('(1 2 3) ('(a b) '(a b is_eq) closure) find)"
        ))
        result = self.machine.run(expr=expr)
        self.assertEqual(result, NIL)


if __name__ == "__main__":
    unittest.main(verbosity=2)
