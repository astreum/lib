import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine
from astreum.expression import NIL
def _is_tagged(expr, tag):
    return (
        expr._tag == "link"
        and expr._tail is not None
        and expr._tail._tag == "symbol"
        and expr._tail.value == tag
    )


class TestOkOperator(unittest.TestCase):
    """ok operator: val -- (val . ok)."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_ok_wraps(self):
        """(42 ok) -> (42 . ok)."""
        expr, _ = parse(tokenize("(42 ok)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "int")
        self.assertEqual(result._head.value, 42)

    def test_ok_wraps_str(self):
        """("hello" ok) -> ("hello" . ok)."""
        expr, _ = parse(tokenize('("hello" ok)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "hello")

    def test_ok_underflow(self):
        """bare (ok) -> OpError caught, pushes NIL."""
        expr, _ = parse(tokenize("(ok)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)


class TestErrOperator(unittest.TestCase):
    """err operator: msg -- (msg . err)."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_err_wraps(self):
        """("bad" err) -> ("bad" . err)."""
        expr, _ = parse(tokenize('("bad" err)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "bad")

    def test_err_underflow(self):
        """bare (err) -> OpError caught, pushes NIL."""
        expr, _ = parse(tokenize("(err)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)


if __name__ == "__main__":
    unittest.main(verbosity=2)