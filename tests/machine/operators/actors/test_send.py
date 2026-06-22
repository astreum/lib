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


class TestSendOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_bare_non_symbol_target(self):
        expr, _ = parse(tokenize("(42 'test send)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_tagged_non_symbol_target(self):
        expr, _ = parse(tokenize("(42 'test send?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "send target must be a symbol")

    def test_bare_unknown_actor(self):
        expr, _ = parse(tokenize("('nonexistent 'msg send)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_tagged_unknown_actor(self):
        expr, _ = parse(tokenize("('nonexistent 'msg send?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "send to unknown actor")

    def test_success_bare(self):
        self.machine.mailboxes["target"] = Queue()
        expr, _ = parse(tokenize("('target 'msg send)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)
        self.assertEqual(self.machine.mailboxes["target"].get().value, "msg")

    def test_success_tagged(self):
        self.machine.mailboxes["target"] = Queue()
        expr, _ = parse(tokenize("('target 'msg send?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Link)
        self.assertIsNone(result.tail.head)
        self.assertIsNone(result.tail.tail)
        self.assertEqual(self.machine.mailboxes["target"].get().value, "msg")


if __name__ == "__main__":
    unittest.main(verbosity=2)
