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


class TestCountOperator(unittest.TestCase):
    """count operator — bytes/str/link element counts; bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bytes ---

    def test_count_bytes(self):
        """(0xff00 count) -> 2 (bytes length)."""
        expr, _ = parse(tokenize("(0xff00 count)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 2)

    def test_count_empty_bytes(self):
        expr, _ = parse(tokenize("(0x count)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 0)

    # --- str ---

    def test_count_str_codepoints(self):
        '''("café" count) -> 4 (codepoints; distinct from byte-size 5).'''
        expr, _ = parse(tokenize('("café" count)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 4)

    def test_count_empty_str(self):
        expr, _ = parse(tokenize('("" count)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 0)

    # --- link ---

    def test_count_link(self):
        """('(a b c d) count) -> 4 (list element count, not tree byte size)."""
        expr, _ = parse(tokenize("('(a b c d) count)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 4)

    def test_count_empty_link(self):
        """(() count) -> 0 (empty list)."""
        expr, _ = parse(tokenize("(() count)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 0)

    def test_count_link_with_nested_elements(self):
        """('((1 2) (3 4) (5)) count) -> 3 (each element counts once regardless of inner size)."""
        expr, _ = parse(tokenize("('((1 2) (3 4) (5)) count)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 3)

    # --- error: non-sequence tags ---

    def test_count_int_returns_nil(self):
        """(42 count) -> NIL (int has no element count)."""
        expr, _ = parse(tokenize("(42 count)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_count_underflow_returns_nil(self):
        """(count) -> NIL."""
        expr, _ = parse(tokenize("(count)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    # --- tagged count ---

    def test_count_bytes_ok_tagged(self):
        expr, _ = parse(tokenize("(0xff00 count?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head.value, 2)

    def test_count_str_ok_tagged(self):
        expr, _ = parse(tokenize('("café" count?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head.value, 4)

    def test_count_link_ok_tagged(self):
        expr, _ = parse(tokenize("('(a b c d) count?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head.value, 4)

    def test_count_err_tagged(self):
        """(42 count?) -> (err . "count of int")."""
        expr, _ = parse(tokenize("(42 count?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head.value, "count of int")

    def test_count_underflow_err_tagged(self):
        """(count?) -> (err . "stack underflow")."""
        expr, _ = parse(tokenize("(count?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
