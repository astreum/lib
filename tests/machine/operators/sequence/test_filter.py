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


class TestFilterOperator(unittest.TestCase):
    """filter operator — keep elements whose fn (truthy per is_truthy) returns truthy."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- link ---

    def test_filter_keep_even_ints(self):
        """('(1 2 3 4) '(2 % 0 is_eq) filter) -> '(2 4)."""
        expr, _ = parse(tokenize("('(1 2 3 4) '(2 % 0 is_eq) filter)"))
        result = self.machine.run(expr=expr)
        self.assertEqual([e.value for e in _collect_link(result)], [2, 4])

    def test_filter_none_match(self):
        """('(1 3 5) '(0 is_eq) filter) -> () — none are equal to 0."""
        expr, _ = parse(tokenize("('(1 3 5) '(0 is_eq) filter)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result, NIL)

    def test_filter_all_match(self):
        """('(1 2 3) '(1 is_eq) filter) — none equal 1, but pick first-match conceptually.
        Use a fn that is always true:
        """
        expr, _ = parse(tokenize("('(1 2 3) '(0 is_eq 0x01 ^) filter)"))
        # '(0 is_eq 0x01 ^) over an int x: x, 0, is_eq=false, 0x01 ^ -> bytes(b'\x01') which is truthy.
        result = self.machine.run(expr=expr)
        self.assertEqual([e.value for e in _collect_link(result)], [1, 2, 3])

    def test_filter_empty_list(self):
        expr, _ = parse(tokenize("(() '(0 is_eq) filter)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result, NIL)

    # --- bytes ---

    def test_filter_bytes_keep_nonzero(self):
        """(0x010001 '(dup) filter) — keep bytes whose dup'd value is truthy.

        For bytes, is_truthy: int.from_bytes != 0. So 0x01 >= 1 byte, encoded int
        is 1, truthy; 0x00 byte gives int 0, not truthy.
        """
        # Body '(dup)': push elem, dup it. Trues per `is_truthy`.
        expr, _ = parse(tokenize("(0x01000100 '(dup) filter)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\x01\x01")

    def test_filter_empty_bytes(self):
        expr, _ = parse(tokenize("(0x '(dup) filter)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"")

    # --- str ---

    def test_filter_str_always_truthy(self):
        '''("abc" '(dup) filter) -> "abc" — for str, is_truthy always true.'''
        expr, _ = parse(tokenize('("abc" \'(dup) filter)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "str")
        self.assertEqual(result.value, "abc")

    # --- error / bad input ---

    def test_filter_non_closure_fn(self):
        expr, _ = parse(tokenize("('(1 2 3) 42 filter)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_filter_non_sequence(self):
        expr, _ = parse(tokenize("(42 '(0 is_eq) filter)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)

    def test_filter_underflow_returns_nil(self):
        expr, _ = parse(tokenize("(filter)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    # --- tagged filter ---

    def test_filter_ok_tagged(self):
        expr, _ = parse(tokenize("('(1 2 3 4) '(2 % 0 is_eq) filter?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual([e.value for e in _collect_link(result._head)], [2, 4])

    def test_filter_err_tagged(self):
        expr, _ = parse(tokenize("('(1 2 3) 42 filter?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))

    def test_filter_underflow_err_tagged(self):
        expr, _ = parse(tokenize("(filter?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head.value, "stack underflow")

    # --- tagged-function fn (lex/dyn/pure) ---

    def test_filter_lex_closure_even_numbers(self):
        """('(1 2 3 4) ('(a) '(a 2 % 0 is_eq) closure) filter) -> '(2 4)."""
        expr, _ = parse(tokenize(
            "('(1 2 3 4) ('(a) '(a 2 % 0 is_eq) closure) filter)"
        ))
        result = self.machine.run(expr=expr)
        self.assertEqual([e.value for e in _collect_link(result)], [2, 4])

    def test_filter_dyn_closure_sees_caller_env(self):
        """dyn-tagged filter fn compares elem to caller-bound threshold."""
        expr, _ = parse(tokenize("(2 'threshold def '(1 2 3 4) '(((a threshold >=) . (a)) . dyn) filter)"))
        result = self.machine.run(expr=expr)
        self.assertEqual([e.value for e in _collect_link(result)], [2, 3, 4])

    def test_filter_pure_closure_isolated(self):
        """Pure fn has no env; threshold unbound -> predicate yields NIL
        (untruthy) for every element -> nothing kept -> NIL. dyn keeps 2 3 4."""
        expr, _ = parse(tokenize("(2 'threshold def '(1 2 3 4) '(((a threshold >=) . (a)) . pure) filter)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result, NIL)

    def test_filter_tagged_wrong_arity_errors(self):
        """Multi-arg tagged filter fn -> OpError -> NIL."""
        expr, _ = parse(tokenize(
            "('(1 2 3) ('(a b) '(a b is_eq) closure) filter)"
        ))
        result = self.machine.run(expr=expr)
        self.assertEqual(result, NIL)


if __name__ == "__main__":
    unittest.main(verbosity=2)
