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


class TestMaybeUnwrap(unittest.TestCase):
    """maybe operator: (val . some) -> val; (none) -> OpError -> NIL."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_unwrap_some_int(self):
        """(42 some maybe) -> 42."""
        expr, _ = parse(tokenize("(42 some maybe)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 42)

    def test_unwrap_some_str(self):
        """"hello" some maybe) -> "hello"."""
        expr, _ = parse(tokenize('("hello" some maybe)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "str")
        self.assertEqual(result.value, "hello")

    def test_unwrap_none(self):
        """(none maybe) -> OpError caught, pushes NIL."""
        expr, _ = parse(tokenize("(none maybe)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_unwrap_not_tagged(self):
        """(42 maybe) -> OpError caught, pushes NIL."""
        expr, _ = parse(tokenize("(42 maybe)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)

    def test_unwrap_unknown_tag(self):
        """(42 ok maybe) -> OpError caught, pushes NIL."""
        expr, _ = parse(tokenize("(42 ok maybe)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)

    def test_chain_two_tagged(self):
        """(5 some maybe 3 some maybe + some) -> (8 . some)."""
        expr, _ = parse(tokenize("(5 some maybe 3 some maybe + some)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "some"))
        self.assertEqual(result._head._tag, "int")
        self.assertEqual(result._head.value, 8)

    def test_chain_none_short_circuit(self):
        """(none maybe) -> NIL."""
        expr, _ = parse(tokenize("(none maybe)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)

    def test_underflow(self):
        """bare (maybe) -> OpError caught, pushes NIL."""
        expr, _ = parse(tokenize("(maybe)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)


class TestSomeOperator(unittest.TestCase):
    """some operator: val -- (val . some)."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_some_wraps(self):
        """(42 some) -> (42 . some)."""
        expr, _ = parse(tokenize("(42 some)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "some"))
        self.assertEqual(result._head._tag, "int")
        self.assertEqual(result._head.value, 42)

    def test_some_wraps_nil(self):
        """(nil some) -> (NIL . some)."""
        expr, _ = parse(tokenize("(nil some)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "some"))
        self.assertEqual(result._head._tag, "link")
        self.assertIsNone(result._head._head)

    def test_some_underflow(self):
        """bare (some) -> OpError caught, pushes NIL."""
        expr, _ = parse(tokenize("(some)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)


class TestNoneOperator(unittest.TestCase):
    """none operator: -- (NIL . none)."""

    def setUp(self):
        self.machine = Machine(node=None)

    def test_none_pushes_none(self):
        """(none) -> (NIL . none)."""
        expr, _ = parse(tokenize("(none)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "none"))
        self.assertEqual(result._head._tag, "link")
        self.assertIsNone(result._head._head)


if __name__ == "__main__":
    unittest.main(verbosity=2)
