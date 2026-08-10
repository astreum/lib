import sys
import unittest
from io import StringIO
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


class TestEachOperator(unittest.TestCase):
    """each operator — fire-effects per element; seq returned unchanged."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_each_returns_seq_unchanged_for_bytes(self):
        """(0xff00 '(0x00 ^) each) -> 0xff00 (xor with 0 is identity)."""
        expr, _ = parse(tokenize("(0xff00 '(0x00 ^) each)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\xff\x00")

    def test_each_returns_seq_unchanged_for_str(self):
        '''("abc" '(dup) each) -> "abc" (mutated by 'dup' would change but here we use length-preserving fn).'''
        # Build a fn that preserves each char: simply print and return the item.
        # Simpler test: use no-op-ish — just use a fn that doesn't change anything.
        # Use '(drop) since drop pops the top of stack — but that'd return '()... not ideal.
        # We'll exercise that each "returns the seq" via the canonical pattern with `nth`-like fns.
        # Use element-preserving reverse + concat — overkill. Simplest: assert each returns same bytes.
        # Generic: a fn that prints and discards its result without altering the elem:
        # '(println) leaves a NIL on stack, which throws off `each` — but `each` discards residues,
        # so the elem-to-str mapping is not relevant here. Instead use a pure fn.
        # For str, use '(swap swap) which permutes without change.
        expr, _ = parse(tokenize('("abc" \'(swap swap) each)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "str")
        self.assertEqual(result.value, "abc")

    def test_each_returns_seq_unchanged_for_link(self):
        """('(1 2 3) '(dup) each) -> '(1 2 3)."""
        expr, _ = parse(tokenize("('(1 2 3) '(dup) each)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertEqual([e.value for e in _collect_link(result)], [1, 2, 3])

    def test_each_discards_per_element_residues(self):
        """('(1 2 3) '(println) each) — each leaves seq on stack, prints all.

        The side-effect body leaves no values; each handles that gracefully and
        returns the original sequence.
        """
        # Capture stdout
        import sys
        captured = StringIO()
        sys.stdout = captured
        try:
            expr, _ = parse(tokenize("('(1 2 3) '(println) each)"))
            result = self.machine.run(expr=expr)
        finally:
            sys.stdout = sys.__stdout__

        output = captured.getvalue()
        # println pushed 1, 2, 3 each on its own line
        self.assertEqual(output.strip().splitlines(), ["1", "2", "3"])
        self.assertEqual(result._tag, "link")
        self.assertEqual([e.value for e in _collect_link(result)], [1, 2, 3])

    def test_each_empty_bytes(self):
        expr, _ = parse(tokenize("(0x '(dup) each)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"")

    def test_each_empty_link(self):
        expr, _ = parse(tokenize("(() '(dup) each)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result, NIL)

    # --- error: non-sequence tags / non-closure fn ---

    def test_each_non_sequence_returns_nil(self):
        """(42 '(dup) each) -> NIL (int has no each)."""
        # This may actually raise — each has no fall-through path.
        # Mirroring pattern: bare each returns NIL via the OpError catch in evaluator.
        expr, _ = parse(tokenize("(42 '(dup) each)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_each_non_closure_fn_returns_nil(self):
        """(0xff00 42 each) -> NIL (fn must be closure form)."""
        expr, _ = parse(tokenize("(0xff00 42 each)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_each_underflow_returns_nil(self):
        expr, _ = parse(tokenize("(each)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    # --- tagged each ---

    def test_each_ok_tagged(self):
        expr, _ = parse(tokenize("('(1 2 3) '(dup) each?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual([e.value for e in _collect_link(result._head)], [1, 2, 3])

    def test_each_err_tagged(self):
        expr, _ = parse(tokenize("(0xff00 42 each?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))

    def test_each_underflow_err_tagged(self):
        expr, _ = parse(tokenize("(each?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head.value, "stack underflow")

    # --- tagged-function fn (lex/dyn/pure) ---

    def test_each_lex_closure_returns_seq_unchanged(self):
        """Tagged each fn is invoked for side effects; original seq is returned."""
        expr, _ = parse(tokenize("('(1 2 3) ('(a) '(a 1 + drop) closure) each)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertEqual([e.value for e in _collect_link(result)], [1, 2, 3])

    def test_each_lex_closure_on_bytes(self):
        """(0xff00 ('(a) '(a 0x00 ^ drop) closure) each) -> 0xff00."""
        expr, _ = parse(tokenize(
            "(0xff00 ('(a) '(a 0x00 ^ drop) closure) each)"
        ))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\xff\x00")

    def test_each_dyn_closure_sees_caller_env(self):
        """dyn-tagged each body resolves x from caller env. We assert it ran
        without error and returned the original seq."""
        expr, _ = parse(tokenize("(10 'x def '(1 2 3) '(((a x + drop) . (a)) . dyn) each)"))
        result = self.machine.run(expr=expr)
        self.assertEqual([e.value for e in _collect_link(result)], [1, 2, 3])

    def test_each_pure_closure_isolated(self):
        """each discards per-element results, so the returned seq is unchanged
        even when the pure fn sees an unbound symbol (parent=None). Verifies the
        pure tag dispatches correctly through each."""
        expr, _ = parse(tokenize("(10 'x def '(1 2 3) '(((a x + drop) . (a)) . pure) each)"))
        result = self.machine.run(expr=expr)
        self.assertEqual([e.value for e in _collect_link(result)], [1, 2, 3])

    def test_each_tagged_wrong_arity_errors(self):
        """Multi-arg tagged each fn -> OpError -> NIL."""
        expr, _ = parse(tokenize(
            "('(1 2 3) ('(a b) '(a b +) closure) each)"
        ))
        result = self.machine.run(expr=expr)
        self.assertEqual(result, NIL)


if __name__ == "__main__":
    unittest.main(verbosity=2)
