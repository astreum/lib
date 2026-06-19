import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


class TestEvaluatorRec(unittest.TestCase):
    """rec — recursive combinator."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_rec_factorial(self):
        """rec computes 5! as 120."""
        expr, _ = parse(tokenize("(5 (' (dup 1 is_eq)) (' (drop 1)) (' (dup 1 -)) (' *) rec)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 120)

    def test_rec_fibonacci(self):
        """rec computes fib(10) as 55."""
        expr, _ = parse(tokenize(
            "(0 1 10 (' (dup 0 is_eq)) (' (swap drop drop)) (' ((' (dup rot +)) dip 1 -)) (' (dup drop)) rec)"
        ))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 55)


if __name__ == "__main__":
    unittest.main(verbosity=2)
