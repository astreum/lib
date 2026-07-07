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
from astreum.machine.models.expression import NIL, int_, fp64_, bytes_, str_, symbol, link


def _is_tagged(expr, tag):
    return (
        expr._tag == "link"
        and expr._tail is not None
        and expr._tail._tag == "symbol"
        and expr._tail.value == tag
    )


class TestReceiveOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_bare_non_symbol_target(self):
        expr, _ = parse(tokenize("(42 receive)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_tagged_non_symbol_target(self):
        expr, _ = parse(tokenize("(42 receive?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "receive target must be a symbol")

    def test_bare_no_mailbox_nil(self):
        expr, _ = parse(tokenize("('nonexistent receive)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_tagged_no_mailbox_ok_nil(self):
        expr, _ = parse(tokenize("('nonexistent receive?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "link")
        self.assertIsNone(result._head._head)
        self.assertIsNone(result._head._tail)

    def test_success_bare(self):
        self.machine.mailboxes["target"] = Queue()
        self.machine.mailboxes["target"].put(int_(42))
        expr, _ = parse(tokenize("('target receive)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 42)

    def test_success_tagged(self):
        self.machine.mailboxes["target"] = Queue()
        self.machine.mailboxes["target"].put(int_(99))
        expr, _ = parse(tokenize("('target receive?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "int")
        self.assertEqual(result._head.value, 99)


if __name__ == "__main__":
    unittest.main(verbosity=2)
