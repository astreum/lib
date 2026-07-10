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


class TestZipOperator(unittest.TestCase):
    """zip operator — list of 2-element link pairs; stops at shortest."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- equal-length same-type list ---

    def test_zip_lists_equal_length(self):
        """('(1 2 3) '(a b c) zip) -> ((1 a) (2 b) (3 c))."""
        expr, _ = parse(tokenize("('(1 2 3) '(a b c) zip)"))
        result = self.machine.run(expr=expr)
        pairs = _collect_link(result)
        self.assertEqual(len(pairs), 3)
        # Pair 0
        self.assertEqual(pairs[0]._head.value, 1)
        self.assertEqual(pairs[0]._tail.value, "a")
        # Pair 2
        self.assertEqual(pairs[2]._head.value, 3)
        self.assertEqual(pairs[2]._tail.value, "c")

    # --- shortest-stop ---

    def test_zip_shortest_stop_a_shorter(self):
        """('(1 2) '(a b c) zip) -> ((1 a) (2 b))."""
        expr, _ = parse(tokenize("('(1 2) '(a b c) zip)"))
        result = self.machine.run(expr=expr)
        pairs = _collect_link(result)
        self.assertEqual(len(pairs), 2)

    def test_zip_shortest_stop_b_shorter(self):
        """('(1 2 3) '(a) zip) -> ((1 a))."""
        expr, _ = parse(tokenize("('(1 2 3) '(a) zip)"))
        result = self.machine.run(expr=expr)
        pairs = _collect_link(result)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]._head.value, 1)
        self.assertEqual(pairs[0]._tail.value, "a")

    # --- empty ---

    def test_zip_empty_a(self):
        expr, _ = parse(tokenize("(() '(a b c) zip)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result, NIL)

    def test_zip_empty_b(self):
        expr, _ = parse(tokenize("('(1 2 3) () zip)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result, NIL)

    # --- heterogeneous containers pair-able (still produce link pairs) ---

    def test_zip_bytes_and_str(self):
        """(0xff41 "xy" zip). Per plan: link-list of 2-element pairs regardless."""
        expr, _ = parse(tokenize('(0xff41 "xy" zip)'))
        result = self.machine.run(expr=expr)
        pairs = _collect_link(result)
        self.assertEqual(len(pairs), 2)
        # (0xff, "x"), (0x41, "y")
        self.assertEqual(pairs[0]._head._tag, "bytes")
        self.assertEqual(pairs[0]._head.value, b"\xff")
        self.assertEqual(pairs[0]._tail.value, "x")

    # --- error: non-sequence ---

    def test_zip_non_sequence(self):
        expr, _ = parse(tokenize("(42 '(a b c) zip)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_zip_underflow_returns_nil(self):
        expr, _ = parse(tokenize("(zip)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    # --- tagged zip ---

    def test_zip_ok_tagged(self):
        expr, _ = parse(tokenize("('(1 2 3) '(a b c) zip?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        pairs = _collect_link(result._head)
        self.assertEqual(len(pairs), 3)

    def test_zip_err_tagged(self):
        expr, _ = parse(tokenize("(42 '(a b c) zip?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))

    def test_zip_underflow_err_tagged(self):
        expr, _ = parse(tokenize("(zip?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
