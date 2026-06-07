"""Tests for right shift operators: SHR (>>>) and SAR (>>).

The parser encodes integer literals as minimal-width signed two's complement
big-endian.  -4 encodes as 1 byte 0xFC.  The operators read/write little-endian
internally (single-byte values are endianness-agnostic).

Operator dispatch (operators/main.py):
  ">>>" → handle_stack_shr   (logical right shift — unsigned, zero fill)
  ">>"  → handle_stack_sar   (arithmetic right shift — sign-extend)
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse  # noqa: E402
from astreum.machine.main import Machine  # noqa: E402


class TestShifts(unittest.TestCase):

    def setUp(self):
        self.machine = Machine(node=None, meter_enabled=False)

    def test_shr_negative_operand(self):
        """(-4 1 >>>) -> 126.
        -4 -> 0xFC.  Read unsigned: 252 >> 1 = 126.
        """
        expr, _ = parse(tokenize("(-4 1 >>>)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 126)

    def test_sar_negative_by_one(self):
        """(-4 1 >>) -> -2.
        -4 = 0xFC.  SAR by 1: 1111_1100 -> 1111_1110 = -2.
        """
        expr, _ = parse(tokenize("(-4 1 >>)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little", signed=True), -2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
