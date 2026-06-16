import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, parse, tokenize  # noqa: E402
from astreum.machine.main import Machine  # noqa: E402
from astreum.machine.models.expression import NIL  # noqa: E402


class TestBytes(unittest.TestCase):

    def setUp(self):
        self.machine = Machine(node=None, meter_enabled=False)

    def test_concat_bytes(self):
        expr, _ = parse(tokenize("(0xab 0xcdef concat)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\xab\xcd\xef")

    def test_existing_bytes_conversion_still_works(self):
        expr, _ = parse(tokenize("(65 bytes)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"A")

    def test_index_first_byte(self):
        expr, _ = parse(tokenize("(0xabcdef 0 index)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\xab")

    def test_index_middle_byte(self):
        expr, _ = parse(tokenize("(0xabcdef 1 index)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\xcd")

    def test_index_last_byte(self):
        expr, _ = parse(tokenize("(0xabcdef 2 index)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\xef")

    def test_index_negative_returns_nil(self):
        expr, _ = parse(tokenize("(0xabcdef -1 index)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result, NIL)

    def test_index_too_large_returns_nil(self):
        expr, _ = parse(tokenize("(0xabcdef 3 index)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result, NIL)

    def test_index_invalid_type_returns_nil(self):
        expr, _ = parse(tokenize("(1 0 index)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result, NIL)

    def test_concat_invalid_type_returns_nil(self):
        expr, _ = parse(tokenize("(0xab 1 concat)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result, NIL)

    def test_split_returns_right_on_top(self):
        expr, _ = parse(tokenize("(0xabcdef 1 split)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\xcd\xef")

    def test_split_left_can_be_kept_by_dropping_right(self):
        expr, _ = parse(tokenize("(0xabcdef 1 split drop)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\xab")

    def test_split_at_zero(self):
        expr, _ = parse(tokenize("(0xabcdef 0 split drop)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"")

    def test_split_at_length(self):
        expr, _ = parse(tokenize("(0xabcdef 3 split)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"")

    def test_split_negative_index_returns_nil(self):
        expr, _ = parse(tokenize("(0xabcdef -1 split)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result, NIL)

    def test_split_too_large_index_returns_nil(self):
        expr, _ = parse(tokenize("(0xabcdef 4 split)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result, NIL)

    def test_split_invalid_type_returns_nil(self):
        expr, _ = parse(tokenize("(1 0 split)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result, NIL)


if __name__ == "__main__":
    unittest.main(verbosity=2)
