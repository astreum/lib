import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


def _is_tagged(expr, tag):
    return (
        expr._tag == "link"
        and expr._tail is not None
        and expr._tail._tag == "symbol"
        and expr._tail.value == tag
    )


class TestBindGeneric(unittest.TestCase):
    """bind operator: tagged ok-tag fail-tag closure -- result."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_bind_generic_ok(self):
        """(42 ok ("ok" symbol) ("err" symbol) 'some bind) -> (42 . some)."""
        expr, _ = parse(tokenize(
            '(42 ok ("ok" symbol) ("err" symbol) \'some bind)'
        ))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "some"))
        self.assertEqual(result._head._tag, "int")
        self.assertEqual(result._head.value, 42)

    def test_bind_generic_err(self):
        """("bad" err ("ok" symbol) ("err" symbol) 'some bind) -> ("bad" . err)."""
        expr, _ = parse(tokenize(
            '("bad" err ("ok" symbol) ("err" symbol) \'some bind)'
        ))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "bad")

    def test_bind_success_tag_not_symbol(self):
        """success tag not a symbol -> OpError caught, NIL."""
        expr, _ = parse(tokenize("(42 ok 10 (\"err\" symbol) 'some bind)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)

    def test_bind_failure_tag_not_symbol(self):
        """failure tag not a symbol -> OpError caught, NIL."""
        expr, _ = parse(tokenize("(42 ok (\"ok\" symbol) 10 'some bind)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)

    def test_bind_failure_tag_not_symbol_alt_expr(self):
        """failure tag non-symbol via alt ordering -> OpError caught, NIL."""
        expr, _ = parse(tokenize("(42 ok 'some 10 (\"ok\" symbol) bind)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)

    def test_bind_underflow(self):
        """bare (bind) -> OpError caught, pushes NIL."""
        expr, _ = parse(tokenize("(bind)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)


if __name__ == "__main__":
    unittest.main(verbosity=2)