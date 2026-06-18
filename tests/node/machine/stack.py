import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


class TestEvaluatorStackOps(unittest.TestCase):
    """drop, dup, swap — stack manipulation."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_drop_removes_top(self):
        """(1 2 drop) -> 1 (top removed)."""
        expr, _ = parse(tokenize("(1 2 drop)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 1)

    def test_drop_underflow_raises(self):
        """() drop raises IndexError."""
        expr, _ = parse(tokenize("(drop)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    def test_dup_duplicates_top(self):
        """(42 dup +) -> 84 (42 + 42)."""
        expr, _ = parse(tokenize("(42 dup +)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 84)

    def test_dup_works_on_list(self):
        """((' (1 2 3)) dup head) -> 1 (duped then head takes top)."""
        expr, _ = parse(tokenize("((' (1 2 3)) dup head)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 1)

    def test_swap_swaps_top_two(self):
        """(1 2 swap) -> top becomes 1 (the former second element)."""
        expr, _ = parse(tokenize("(1 2 swap)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 1)

    def test_swap_drop_chain(self):
        """(3 4 swap drop) -> 4 (swap makes 4 top, then drop removes old top)."""
        expr, _ = parse(tokenize("(3 4 swap drop)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 4)

    def test_rot_rotates_top_three(self):
        """(1 2 3 rot) -> 1 (top three become 2 3 1, top of final stack is 1)."""
        expr, _ = parse(tokenize("(1 2 3 rot)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 1)

    def test_rot_underflow_returns_nil(self):
        """(1 2 rot) -> NIL."""
        expr, _ = parse(tokenize("(1 2 rot)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
