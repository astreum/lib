import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine


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


class TestLoad(unittest.TestCase):
    def test_load_no_node(self):
        machine = Machine(node=None)
        expr = _load_expr(b"\x00" * 32)
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)

    def test_load_missing_hash(self):
        node = FakeNode()
        machine = Machine(node=node)
        expr = _load_expr(b"\xde\xad\xbe\xef" * 8)
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)

    def test_load_wrong_input_not_bytes(self):
        node = FakeNode()
        machine = Machine(node=node)
        expr, _ = parse(tokenize('("hello" load)'))
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)

    def test_load_wrong_input_wrong_size(self):
        node = FakeNode()
        machine = Machine(node=node)
        expr = Expr.Link(Expr.Bytes(b"\x01"), Expr.Link(Expr.Symbol("load"), None))
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)

    def test_load_empty_stack(self):
        node = FakeNode()
        machine = Machine(node=node)
        expr = Expr.Link(Expr.Symbol("load"), None)
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)

    def test_load_resolves_bytes(self):
        stored = Expr.Bytes(b"\x01\x02\x03")
        h = stored.hash()

        node = FakeNode()
        node.hot_storage[h] = stored

        machine = Machine(node=node)
        expr = _load_expr(h)
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x01\x02\x03")

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

    def test_load_link_head_tail_direct(self):
        stored = Expr.Link(Expr.Bytes(b"\x01"), Expr.Bytes(b"\x02"))
        h = stored.hash()

        node = FakeNode()
        node.hot_storage[h] = stored

        machine = Machine(node=node)
        # (h load head) — head on concrete link, no eval needed
        expr = Expr.Link(
            Expr.Bytes(h),
            Expr.Link(Expr.Symbol("load"),
                Expr.Link(Expr.Symbol("head"), None)))
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x01")

    def test_load_deep_tree(self):
        leaf1 = Expr.Bytes(b"\xaa")
        leaf2 = Expr.Bytes(b"\xbb")
        leaf3 = Expr.Bytes(b"\xcc")
        inner = Expr.Link(leaf2, leaf3)
        root = Expr.Link(leaf1, inner)
        h = root.hash()

        node = FakeNode()
        node.hot_storage[h] = root
        node.hot_storage[leaf1.hash()] = leaf1
        node.hot_storage[inner.hash()] = inner
        node.hot_storage[leaf2.hash()] = leaf2
        node.hot_storage[leaf3.hash()] = leaf3

        machine = Machine(node=node)
        expr = _load_expr(h)
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsInstance(result.head, Expr.Bytes)
        self.assertEqual(result.head.value, b"\xaa")
        self.assertIsInstance(result.tail, Expr.Link)
        self.assertIsInstance(result.tail.head, Expr.Bytes)
        self.assertEqual(result.tail.head.value, b"\xbb")
        self.assertIsInstance(result.tail.tail, Expr.Bytes)
        self.assertEqual(result.tail.tail.value, b"\xcc")

    def test_load_link_from_hashes_only(self):
        bytes_val = Expr.Bytes(b"\xaa")
        head_h = bytes_val.hash()
        stored = Expr.Link(head_hash=head_h, tail_hash=None)
        h = stored.hash()

        node = FakeNode()
        node.hot_storage[h] = stored
        node.hot_storage[head_h] = bytes_val

        machine = Machine(node=node)
        expr = _load_expr(h)
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsInstance(result.head, Expr.Bytes)
        self.assertEqual(result.head.value, b"\xaa")

    def test_load_deep_missing_child_returns_nil(self):
        leaf1 = Expr.Bytes(b"\xaa")
        leaf2 = Expr.Bytes(b"\xbb")
        # Link with hash-only pointer to leaf2 — concrete children not attached
        inner = Expr.Link(leaf1, tail_hash=leaf2.hash())
        h = inner.hash()

        node = FakeNode()
        node.hot_storage[h] = inner
        node.hot_storage[leaf1.hash()] = leaf1
        # leaf2 not stored by hash — resolve tail_hash should fail

        machine = Machine(node=node)
        expr = _load_expr(h)
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)

    def test_load_meter_double_size(self):
        stored = Expr.Link(Expr.Bytes(b"\x01"), Expr.Bytes(b"\x02"))
        h = stored.hash()

        node = FakeNode()
        node.hot_storage[h] = stored

        machine = Machine(node=node, meter_enabled=True)
        expr = _load_expr(h)
        machine.run(expr=expr)
        self.assertEqual(machine.meter.used, stored.size() * 2 + 32)

    def test_load_meter_bytes(self):
        stored = Expr.Bytes(b"\x01\x02\x03")
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
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x01\x02\x03")


if __name__ == "__main__":
    unittest.main(verbosity=2)
