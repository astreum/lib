import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


class TestEvaluatorDefAndLookup(unittest.TestCase):
    """def binding and symbol resolution."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_def_then_lookup_resolves(self):
        """((7 (quote seven) def) seven) -> stack has [7]."""
        expr, _ = parse(tokenize("((7 (quote seven) def) seven)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 7)

    def test_def_overwrites(self):
        """((5 (quote x) def) (99 (quote x) def) x) -> second def wins."""
        expr, _ = parse(tokenize("((5 (quote x) def) (99 (quote x) def) x)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(int.from_bytes(result.value, "little"), 99)

    def test_unbound_symbol_yields_nil(self):
        """An undefined symbol pushes nil (Link(None,None))."""
        expr, _ = parse(tokenize("undefined_symbol"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
