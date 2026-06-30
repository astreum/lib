import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine
from astreum.machine.models.expression import NIL, int_, float_, bytes_, str_, symbol, link


def _is_tagged(expr, tag):
    return (
        expr._tag == "link"
        and expr._tail is not None
        and expr._tail._tag == "symbol"
        and expr._tail.value == tag
    )


class TestDefOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    # --- bare (no ?) ---

    def test_bare_def_success(self):
        expr, _ = parse(tokenize("(42 'x def)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    def test_bare_def_binds_value(self):
        expr, _ = parse(tokenize("(42 'x def x)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 42)

    def test_bare_def_underflow_returns_nil(self):
        expr, _ = parse(tokenize("(def)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    def test_bare_def_not_symbol_returns_nil(self):
        expr, _ = parse(tokenize("(42 99 def)"))
        result = self.machine.run(expr=expr)
        self.assertIs(result, NIL)

    def test_bare_def_already_exists_returns_nil(self):
        machine = Machine(node=None)
        machine.run(parse(tokenize("(42 'x def)"))[0])
        expr, _ = parse(tokenize("(99 'x def)"))
        result = machine.run(expr=expr)
        self.assertIs(result, NIL)

    def test_bare_def_first_binding_preserved(self):
        machine = Machine(node=None)
        machine.run(parse(tokenize("(42 'x def)"))[0])
        machine.run(parse(tokenize("(7 'x def)"))[0])
        expr, _ = parse(tokenize("(x)"))
        result = machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 42)

    # --- tagged (?) ---

    def test_tagged_def_success_returns_ok_nil(self):
        expr, _ = parse(tokenize("(42 'x def?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIs(result._head, NIL)

    def test_tagged_def_binds_value(self):
        expr, _ = parse(tokenize("(42 'x def? x)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 42)

    def test_tagged_def_underflow_returns_err(self):
        expr, _ = parse(tokenize("(def?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "stack underflow")

    def test_tagged_def_not_symbol_returns_err(self):
        expr, _ = parse(tokenize("(42 99 def?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "def of int")

    def test_tagged_def_already_exists_returns_err(self):
        machine = Machine(node=None)
        machine.run(parse(tokenize("(42 'x def)"))[0])
        expr, _ = parse(tokenize("(7 'x def?)"))
        result = machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "def already exists")


if __name__ == "__main__":
    unittest.main(verbosity=2)
