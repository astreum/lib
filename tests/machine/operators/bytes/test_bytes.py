import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine
from astreum.machine.models.expression import NIL


def _is_tagged(expr, tag):
    return (
        isinstance(expr, Expr.Link)
        and isinstance(expr.head, Expr.Symbol)
        and expr.head.value == tag
    )


class TestBytesConversionOperator(unittest.TestCase):
    """bytes conversion operator — bare and tagged (?)."""

    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare bytes ---

    def test_bytes_from_int(self):
        expr, _ = parse(tokenize("(42 bytes)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)

    def test_bytes_from_float(self):
        expr, _ = parse(tokenize("(3.14 bytes)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)

    def test_bytes_from_string(self):
        expr, _ = parse(tokenize('("hello" bytes)'))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)

    def test_bytes_from_bytes(self):
        expr, _ = parse(tokenize("(0xdead bytes)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\xde\xad")

    def test_bytes_link_returns_nil(self):
        """(foo bytes) -> NIL (unbound symbol pushes NIL, bytes fails on Link)."""
        expr, _ = parse(tokenize("(foo bytes)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_bytes_underflow_raises(self):
        expr, _ = parse(tokenize("(bytes)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    # --- tagged bytes (?) ---

    def test_bytes_int_ok(self):
        expr, _ = parse(tokenize("(42 bytes?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Bytes)

    def test_bytes_link_err(self):
        """(foo bytes?) -> (err . "bytes of link") (unbound symbol pushes NIL/Link)."""
        expr, _ = parse(tokenize("(foo bytes?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "bytes of link")

    def test_bytes_underflow_err(self):
        expr, _ = parse(tokenize("(bytes?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
