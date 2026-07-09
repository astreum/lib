import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine
from astreum.expression import NIL, int_, symbol, link


class TestOperatorOverride(unittest.TestCase):
    """Test that user def bindings can shadow monadic operators."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_try_overridden_with_value(self):
        """def shadows try in non-det mode: try resolves to 42, not the operator."""
        expr, _ = parse(tokenize("(42 'try def '(\"fail\") try)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 42)

    def test_ok_overridden_with_value(self):
        """def shadows ok in non-det mode: ok resolves to 99, not the constructor."""
        expr, _ = parse(tokenize("(99 'ok def 5 ok)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 99)

    def test_err_overridden_with_value(self):
        """def shadows err in non-det mode: err resolves to symbol, not the constructor."""
        expr, _ = parse(tokenize("('custom_msg 'err def 5 err)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "symbol")
        self.assertEqual(result.value, "custom_msg")


if __name__ == "__main__":
    unittest.main(verbosity=2)
