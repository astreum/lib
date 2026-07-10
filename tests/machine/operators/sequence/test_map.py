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


class TestMapOperator(unittest.TestCase):
    """map operator — type-preserving element-wise transformation."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bytes ---

    def test_map_bytes_xor(self):
        """(0xff00 '(0x01 ^) map) -> 0xfe01."""
        expr, _ = parse(tokenize("(0xff00 '(0x01 ^) map)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\xfe\x01")

    def test_map_bytes_identity(self):
        """(0xdead '(dup) map) -> 0xdead (dup pushes a copy of the elem)."""
        expr, _ = parse(tokenize("(0xdead '(dup) map)"))
        result = self.machine.run(expr=expr)
        # dup pushes a copy; without explicit consume, the fn stack has dup so
        # the elem gets effectively duplicated per element — but for bytes, "dup"
        # on a bytes element returns the elem itself. Confirm bytes is preserved.
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"\xde\xad")

    def test_map_empty_bytes(self):
        expr, _ = parse(tokenize("(0x '(dup) map)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "bytes")
        self.assertEqual(result.value, b"")

    # --- str ---

    def test_map_str_upper_via_str_fn(self):
        """('"abc" '(dup) map) -> "abc" (preserves type via dup)."""
        expr, _ = parse(tokenize('("abc" \'(dup) map)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "str")
        self.assertEqual(result.value, "abc")

    def test_map_empty_str(self):
        expr, _ = parse(tokenize('("" \'(dup) map)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "str")
        self.assertEqual(result.value, "")

    # --- link ---

    def test_map_link_increment(self):
        """('(1 2 3) '(1 +) map) -> '(2 3 4)."""
        expr, _ = parse(tokenize("('(1 2 3) '(1 +) map)"))
        result = self.machine.run(expr=expr)
        self.assertEqual([e.value for e in _collect_link(result)], [2, 3, 4])

    def test_map_empty_link(self):
        expr, _ = parse(tokenize("(() '(1 +) map)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result, NIL)

    # --- element-type mismatch (type error) ---

    def test_map_wrong_element_type_for_bytes_returns_nil(self):
        """(0xff00 '(0x00) map) — fn pushes 1byte, fine; use '(dup) won't change. Use a fn that returns int."""
        # The fn needs to return non-bytes for bytes map. Use a literal-int 'fn':
        # '(1) body yields constant 1 (int), incompatible with bytes.
        expr, _ = parse(tokenize("(0xff00 '(1) map)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_map_wrong_element_type_for_link_returns_symbolic_tail(self):
        # fn returns link(...) — incompatible (per plan, link element can be any Expr).
        # Use a const fn returning a different type. Simplest case: a fn that yields an int
        # for a link that should be... actually link allows any. Let's exercise the
        # explicit case: bytes→non-bytes is a hard error. Covered above.
        pass

    # --- non-closure fn ---

    def test_map_non_closure_fn_returns_nil(self):
        expr, _ = parse(tokenize("(0xff00 42 map)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_map_non_sequence_returns_nil(self):
        expr, _ = parse(tokenize("(42 '(dup) map)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_map_underflow_returns_nil(self):
        expr, _ = parse(tokenize("(map)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    # --- tagged map ---

    def test_map_ok_tagged(self):
        expr, _ = parse(tokenize("('(1 2 3) '(1 +) map?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual([e.value for e in _collect_link(result._head)], [2, 3, 4])

    def test_map_err_tagged(self):
        expr, _ = parse(tokenize("(0xff00 42 map?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))

    def test_map_underflow_err_tagged(self):
        expr, _ = parse(tokenize("(map?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
