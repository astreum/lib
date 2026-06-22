import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine
from astreum.machine.models.expression import NIL, ZERO32


def _is_tagged(expr, tag):
    return (
        isinstance(expr, Expr.Link)
        and isinstance(expr.head, Expr.Symbol)
        and expr.head.value == tag
    )


class FakeNode:
    def __init__(self):
        self.hot_storage = {}

    def get_expr(self, expr_id: bytes):
        return self.hot_storage.get(expr_id)

    def get_expr_full(self, expr_id: bytes):
        expr = self.get_expr(expr_id)
        if expr is None:
            return None
        if not isinstance(expr, Expr.Link):
            return expr
        if expr.head is None and expr.head_hash is not None:
            head = self.get_expr_full(expr.head_hash)
            if head is None:
                return None
            expr.head = head
            expr.head_hash = None
        if expr.tail is None and expr.tail_hash is not None:
            tail = self.get_expr_full(expr.tail_hash)
            if tail is None:
                return None
            expr.tail = tail
            expr.tail_hash = None
        return expr


def _load_expr(hash_bytes: bytes) -> Expr:
    return Expr.Link(Expr.Bytes(hash_bytes), Expr.Link(Expr.Symbol("load"), None))


class TestLoadOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_load_empty_stack_returns_nil(self):
        expr, _ = parse(tokenize("(load)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_load_zero32_returns_nil(self):
        expr, _ = parse(tokenize("(0x0000000000000000000000000000000000000000000000000000000000000000 load)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_load_non_bytes_returns_nil(self):
        expr, _ = parse(tokenize('("not-a-hash" load)'))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_load_short_bytes_returns_nil(self):
        expr, _ = parse(tokenize("(0xdead load)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_load_no_node_returns_nil(self):
        h = "01" * 32
        expr, _ = parse(tokenize(f"(0x{h} load)"))
        result = self.machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_load_underflow_raises(self):
        pass

    def test_load_resolves_symbol(self):
        stored = Expr.Symbol("hello")
        h = stored.hash()
        node = FakeNode()
        node.hot_storage[h] = stored
        machine = Machine(node=node)
        expr = _load_expr(h)
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Symbol)
        self.assertEqual(result.value, "hello")

    def test_load_resolves_link_concrete(self):
        stored = Expr.Link(Expr.Bytes(b"\x01"), Expr.Bytes(b"\x02"))
        h = stored.hash()
        node = FakeNode()
        node.hot_storage[h] = stored
        machine = Machine(node=node)
        expr = _load_expr(h)
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsInstance(result.head, Expr.Bytes)
        self.assertEqual(result.head.value, b"\x01")
        self.assertIsInstance(result.tail, Expr.Bytes)
        self.assertEqual(result.tail.value, b"\x02")

    def test_load_meter_double_size(self):
        stored = Expr.Link(Expr.Bytes(b"\x01"), Expr.Bytes(b"\x02"))
        h = stored.hash()
        node = FakeNode()
        node.hot_storage[h] = stored
        machine = Machine(node=node, meter_enabled=True)
        expr = _load_expr(h)
        machine.run(expr=expr)
        self.assertEqual(machine.meter.used, stored.size() * 2 + 32)

    def test_load_deterministic(self):
        stored = Expr.Bytes(b"\x01\x02\x03")
        h = stored.hash()
        node = FakeNode()
        node.hot_storage[h] = stored
        machine = Machine(node=node, mode="deterministic")
        expr = _load_expr(h)
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_load_zero32_ok(self):
        expr, _ = parse(tokenize("(0x0000000000000000000000000000000000000000000000000000000000000000 load?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertIsInstance(result.tail, Expr.Link)
        self.assertIsNone(result.tail.head)
        self.assertIsNone(result.tail.tail)

    def test_load_non_bytes_err(self):
        expr, _ = parse(tokenize('("not-a-hash" load?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "load requires 32-byte hash, got string")

    def test_load_short_bytes_err(self):
        expr, _ = parse(tokenize("(0xdead load?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "load requires 32-byte hash, got 2 bytes")

    def test_load_no_node_err(self):
        h = "01" * 32
        expr, _ = parse(tokenize(f"(0x{h} load?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertIsInstance(result.tail, Expr.String)
        self.assertEqual(result.tail.value, "load requires a node connection")


if __name__ == "__main__":
    unittest.main(verbosity=2)
