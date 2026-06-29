import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine
from astreum.machine.models.expression import NIL, int_, float_, bytes_, str_, symbol, link


def _is_tagged(expr, tag):
    return (
        expr._tag == "link"
        and expr._head._tag == "symbol"
        and expr._head.value == tag
    )


class TestStrOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_str_from_bytes(self):
        expr, _ = parse(tokenize('(0x68656c6c6f str)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "str")
        self.assertEqual(result.value, "hello")

    def test_str_from_int(self):
        expr, _ = parse(tokenize("(42 str)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "str")
        self.assertEqual(result.value, "42")

    def test_str_from_float(self):
        expr, _ = parse(tokenize("(3.14 str)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "str")
        self.assertEqual(result.value, "3.14")

    def test_str_identity(self):
        expr, _ = parse(tokenize('("hello" str)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "str")
        self.assertEqual(result.value, "hello")

    def test_str_non_atom_returns_nil(self):
        expr, _ = parse(tokenize("(1 2 link str)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_str_underflow_raises(self):
        expr, _ = parse(tokenize("(str)"))
        with self.assertRaises(IndexError):
            self.machine.run(expr=expr)

    def test_str_from_bytes_ok(self):
        expr, _ = parse(tokenize('(0x68656c6c6f str?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "hello")

    def test_str_utf8_err(self):
        expr, _ = parse(tokenize("(0x80ff str?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "str: bytes are not valid UTF-8")

    def test_str_non_atom_err(self):
        expr, _ = parse(tokenize("(1 2 link str?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "str of link")

    def test_str_underflow_err(self):
        expr, _ = parse(tokenize("(str?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._tail._tag, "str")
        self.assertEqual(result._tail.value, "stack underflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
