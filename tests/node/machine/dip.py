import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


class TestEvaluatorDip(unittest.TestCase):
    """dip — hide a value, evaluate a quotation, restore the value."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_dip_basic(self):
        """(3 4 (' (dup mul)) dip) -> 4 top, 9 under (hide 4, dup*mul on 3)."""
        expr, _ = parse(tokenize("(3 4 (' (dup mul)) dip)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 4)

    def test_dip_with_drop(self):
        """(1 2 3 (' drop) dip +) -> 4 (hide 3, drop 2, restore 3, 1+3)."""
        expr, _ = parse(tokenize("(1 2 3 (' drop) dip +)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 4)

    def test_dip_underflow(self):
        """(dip) raises IndexError."""
        expr, _ = parse(tokenize("(dip)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
