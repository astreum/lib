import sys
import unittest
from pathlib import Path
from queue import Queue

ROOT = Path(__file__).resolve().parents[4]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


def _is_tagged(expr, tag):
    return (
        isinstance(expr, Expr.Link)
        and isinstance(expr.head, Expr.Symbol)
        and expr.head.value == tag
    )


class TestReceiveOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_bare_non_symbol_target(self):
        expr, _ = parse(tokenize("(42 receive)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_tagged_non_symbol_target(self):
        expr, _ = parse(tokenize("(42 receive?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "receive target must be a symbol")

    def test_bare_no_mailbox_nil(self):
        expr, _ = parse(tokenize("('nonexistent receive)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_tagged_no_mailbox_ok_nil(self):
        expr, _ = parse(tokenize("('nonexistent receive?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Link)
        self.assertIsNone(result.tail.head)
        self.assertIsNone(result.tail.tail)

    def test_success_bare(self):
        self.machine.mailboxes["target"] = Queue()
        self.machine.mailboxes["target"].put(Expr.Int(42))
        expr, _ = parse(tokenize("('target receive)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Int)
        self.assertEqual(result.value, 42)

    def test_success_tagged(self):
        self.machine.mailboxes["target"] = Queue()
        self.machine.mailboxes["target"].put(Expr.Int(99))
        expr, _ = parse(tokenize("('target receive?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Int)
        self.assertEqual(result.tail.value, 99)


if __name__ == "__main__":
    unittest.main(verbosity=2)
