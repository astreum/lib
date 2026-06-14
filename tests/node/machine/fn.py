import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


class TestEvaluatorFn(unittest.TestCase):
    """fn — inline function application.

    fn pops: body (top), then params (next). So the expression order is:
    (args... (' params) (' body) fn)
    """

    def setUp(self):
        self.machine = Machine(node=None)

    def test_fn_add_two_numbers(self):
        """(3 5 (' ($0 $1)) (' ($0 $1 +)) fn) -> 8."""
        expr, _ = parse(tokenize("(3 5 (' ($0 $1)) (' ($0 $1 +)) fn)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 8)

    def test_fn_three_args(self):
        """(10 20 30 (' ($0 $1 $2)) (' ($0 $1 $2 + +)) fn) -> 60."""
        expr, _ = parse(tokenize(
            "(10 20 30 (' ($0 $1 $2)) (' ($0 $1 $2 + +)) fn)"
        ))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 60)

    def test_fn_nested_call(self):
        """((3 5 (' ($0 $1)) (' ($0 $1 +)) fn) 2 +) -> 10."""
        expr, _ = parse(tokenize(
            "((3 5 (' ($0 $1)) (' ($0 $1 +)) fn) 2 +)"
        ))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
