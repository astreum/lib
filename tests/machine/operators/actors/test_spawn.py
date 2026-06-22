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


class TestSpawnOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_bare_non_symbol_name(self):
        expr, _ = parse(tokenize("('myactor 42 spawn)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_tagged_non_symbol_name(self):
        expr, _ = parse(tokenize("('myactor 42 spawn?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "spawn actor name must be a symbol")

    def test_bare_non_link_body(self):
        expr, _ = parse(tokenize("(42 'good spawn)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_tagged_non_link_body(self):
        expr, _ = parse(tokenize("(42 'good spawn?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "spawn body must be a link")

    def test_bare_spawn_failure(self):
        self.machine.mailboxes["existing"] = Queue()
        expr, _ = parse(tokenize("('() 'existing spawn)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_tagged_spawn_failure(self):
        self.machine.mailboxes["existing"] = Queue()
        expr, _ = parse(tokenize("('() 'existing spawn?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "spawn failed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
