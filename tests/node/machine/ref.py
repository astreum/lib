import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine
from astreum.machine.models.expression import ZERO32


class FakeNode:
    def __init__(self):
        self.hot_storage = {}

    def get_expr(self, expr_id: bytes):
        return self.hot_storage.get(expr_id)


def _ref_expr(hash_bytes: bytes) -> Expr:
    return Expr.Link(Expr.Bytes(hash_bytes), Expr.Symbol("ref"))


class TestRef(unittest.TestCase):
    def test_ref_no_node(self):
        machine = Machine(node=None)
        expr = _ref_expr(b"\x00" * 32)
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)

    def test_ref_missing_hash(self):
        node = FakeNode()
        machine = Machine(node=node)
        expr = _ref_expr(b"\xde\xad\xbe\xef" * 8)
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)

    def test_ref_wrong_input_not_bytes(self):
        node = FakeNode()
        machine = Machine(node=node)
        expr, _ = parse(tokenize('("hello" ref)'))
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)

    def test_ref_wrong_input_wrong_size(self):
        node = FakeNode()
        machine = Machine(node=node)
        expr = Expr.Link(Expr.Bytes(b"\x01"), Expr.Symbol("ref"))
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)

    def test_ref_empty_stack(self):
        node = FakeNode()
        machine = Machine(node=node)
        expr = Expr.Link(Expr.Symbol("ref"), None)
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)

    def test_ref_resolves_bytes(self):
        stored = Expr.Bytes(b"\x01\x02\x03")
        h = stored.hash()

        node = FakeNode()
        node.hot_storage[h] = stored

        machine = Machine(node=node)
        expr = _ref_expr(h)
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x01\x02\x03")

    def test_ref_resolves_symbol(self):
        stored = Expr.Symbol("hello")
        h = stored.hash()

        node = FakeNode()
        node.hot_storage[h] = stored

        machine = Machine(node=node)
        expr = _ref_expr(h)
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Symbol)
        self.assertEqual(result.value, "hello")

    def test_ref_resolves_link_produces_thunks(self):
        stored = Expr.Link(Expr.Bytes(b"\x01"), Expr.Bytes(b"\x02"))
        h = stored.hash()
        expected_head_h = stored.head.hash()
        expected_tail_h = stored.tail.hash()

        node = FakeNode()
        node.hot_storage[h] = stored
        node.hot_storage[expected_head_h] = stored.head
        node.hot_storage[expected_tail_h] = stored.tail

        machine = Machine(node=node)
        expr = _ref_expr(h)
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNotNone(result.head)
        self.assertIsNotNone(result.tail)

        # head should be a thunk: (head_h ref)
        head_thunk = result.head
        self.assertIsInstance(head_thunk, Expr.Link)
        self.assertIsInstance(head_thunk.head, Expr.Bytes)
        self.assertEqual(head_thunk.head.value, expected_head_h)
        self.assertIsInstance(head_thunk.tail, Expr.Symbol)
        self.assertEqual(head_thunk.tail.value, "ref")

        # tail should be a thunk: (tail_h ref)
        tail_thunk = result.tail
        self.assertIsInstance(tail_thunk, Expr.Link)
        self.assertIsInstance(tail_thunk.head, Expr.Bytes)
        self.assertEqual(tail_thunk.head.value, expected_tail_h)
        self.assertIsInstance(tail_thunk.tail, Expr.Symbol)
        self.assertEqual(tail_thunk.tail.value, "ref")

    def test_ref_head_eval_chain(self):
        stored = Expr.Link(Expr.Bytes(b"\x01"), Expr.Bytes(b"\x02"))
        h = stored.hash()

        node = FakeNode()
        node.hot_storage[h] = stored
        node.hot_storage[stored.head.hash()] = stored.head
        node.hot_storage[stored.tail.hash()] = stored.tail

        machine = Machine(node=node)
        # (h ref head eval) — resolves link, gets head thunk, evaluates it
        expr = Expr.Link(
            Expr.Bytes(h),
            Expr.Link(Expr.Symbol("ref"),
                Expr.Link(Expr.Symbol("head"),
                    Expr.Link(Expr.Symbol("eval"), None))))
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x01")

    def test_ref_tail_eval_chain(self):
        stored = Expr.Link(Expr.Bytes(b"\x01"), Expr.Bytes(b"\x02"))
        h = stored.hash()

        node = FakeNode()
        node.hot_storage[h] = stored
        node.hot_storage[stored.head.hash()] = stored.head
        node.hot_storage[stored.tail.hash()] = stored.tail

        machine = Machine(node=node)
        # (h ref tail eval) — resolves link, gets tail thunk, evaluates it
        expr = Expr.Link(
            Expr.Bytes(h),
            Expr.Link(Expr.Symbol("ref"),
                Expr.Link(Expr.Symbol("tail"),
                    Expr.Link(Expr.Symbol("eval"), None))))
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\x02")

    def test_ref_nil_link_returns_nil(self):
        stored = Expr.Link(None, None)
        h = stored.hash()
        self.assertEqual(h, ZERO32)

        node = FakeNode()
        node.hot_storage[h] = stored

        machine = Machine(node=node)
        expr = _ref_expr(h)
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)

    def test_ref_link_from_hashes_only(self):
        bytes_val = Expr.Bytes(b"\xaa")
        head_h = bytes_val.hash()
        stored = Expr.Link(head_hash=head_h, tail_hash=ZERO32)
        h = stored.hash()

        node = FakeNode()
        node.hot_storage[h] = stored
        node.hot_storage[head_h] = bytes_val

        machine = Machine(node=node)
        # ref the link, then head + eval to dereference
        expr = Expr.Link(
            Expr.Bytes(h),
            Expr.Link(Expr.Symbol("ref"),
                Expr.Link(Expr.Symbol("head"),
                    Expr.Link(Expr.Symbol("eval"), None))))
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Bytes)
        self.assertEqual(result.value, b"\xaa")

    def test_ref_meter_link_fixed_70(self):
        stored = Expr.Link(Expr.Bytes(b"\x01"), Expr.Bytes(b"\x02"))
        h = stored.hash()

        node = FakeNode()
        node.hot_storage[h] = stored

        machine = Machine(node=node, meter_enabled=True)
        expr = _ref_expr(h)
        machine.run(expr=expr)
        self.assertEqual(machine.meter.used, 70 + 32)

    def test_ref_meter_bytes_sized(self):
        stored = Expr.Bytes(b"\x01\x02\x03")
        h = stored.hash()

        node = FakeNode()
        node.hot_storage[h] = stored

        machine = Machine(node=node, meter_enabled=True)
        expr = _ref_expr(h)
        machine.run(expr=expr)
        self.assertEqual(machine.meter.used, stored.size() + 32)

    def test_ref_deterministic(self):
        stored = Expr.Bytes(b"\x01\x02\x03")
        h = stored.hash()

        node = FakeNode()
        node.hot_storage[h] = stored

        machine = Machine(node=node, mode="deterministic")
        expr = _ref_expr(h)
        result = machine.run(expr=expr)
        self.assertIsInstance(result, Expr.Link)
        self.assertIsNone(result.head)
        self.assertIsNone(result.tail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
