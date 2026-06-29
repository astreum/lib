from astreum.machine.main import Machine
from astreum.machine.parser import parse
from astreum.machine.tokenizer import tokenize
from astreum.machine.models.expression import Expr, int_, float_, str_, symbol, bytes_, link, NIL

import unittest


class TestInitOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None, mode="deterministic")

    def test_init_new_tag(self):
        """(3 'point init) -> Expr("point", value=3)."""
        expr, _ = parse(tokenize("(3 'point init)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "point")
        self.assertEqual(result._value._tag, "int")
        self.assertEqual(result._value.value, 3)

    def test_init_idempotent(self):
        """(42 'int init) -> Int(42) (idempotent)."""
        expr, _ = parse(tokenize("(42 'int init)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "int")
        self.assertEqual(result.value, 42)

    def test_init_link_identity(self):
        """((3 5 link) 'link init) -> same link (identity)."""
        expr, _ = parse(tokenize("((3 5 link) 'link init)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertEqual(result._head.value, 3)

    def test_init_tag_symbol(self):
        """('hello 'symbol init) -> Symbol("hello") (idempotent)."""
        expr, _ = parse(tokenize("('hello 'symbol init)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "symbol")
        self.assertEqual(result.value, "hello")

    def test_init_rejects_non_symbol_tag(self):
        """(42 3 init) -> NIL (error caught, tag must be symbol)."""
        expr, _ = parse(tokenize("(42 3 init)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_init_underflow(self):
        """(init) -> NIL (error caught, stack underflow)."""
        expr, _ = parse(tokenize("(init)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)


class TestTypeOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None, mode="deterministic")

    def test_type_int(self):
        """(42 type) -> Symbol("int")."""
        expr, _ = parse(tokenize("(42 type)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "symbol")
        self.assertEqual(result.value, "int")

    def test_type_float(self):
        """(3.14 type) -> Symbol("float")."""
        expr, _ = parse(tokenize("(3.14 type)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "symbol")
        self.assertEqual(result.value, "float")

    def test_type_str(self):
        """("hello" type) -> Symbol("str")."""
        expr, _ = parse(tokenize('("hello" type)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "symbol")
        self.assertEqual(result.value, "str")

    def test_type_symbol(self):
        """('x type) -> Symbol("symbol")."""
        expr, _ = parse(tokenize("('x type)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "symbol")
        self.assertEqual(result.value, "symbol")

    def test_type_link(self):
        """((3 5 link) type) -> Symbol("link")."""
        expr, _ = parse(tokenize("((3 5 link) type)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "symbol")
        self.assertEqual(result.value, "link")

    def test_type_user_type(self):
        """((3 'point init) type) -> Symbol("point")."""
        expr, _ = parse(tokenize("((3 'point init) type)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "symbol")
        self.assertEqual(result.value, "point")

    def test_type_underflow(self):
        """(type) -> NIL (error caught, stack underflow)."""
        expr, _ = parse(tokenize("(type)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)


if __name__ == "__main__":
    unittest.main()
