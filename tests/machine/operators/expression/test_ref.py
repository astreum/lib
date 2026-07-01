import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine
from astreum.machine.models.expression import NIL, ZERO32, int_, float_, bytes_, str_, symbol, link


def _is_tagged(expr, tag):
    return (
        expr._tag == "link"
        and expr._tail is not None
        and expr._tail._tag == "symbol"
        and expr._tail.value == tag
    )


class FakeNode:
    def __init__(self):
        self.hot_storage = {}

    def get_expr(self, expr_id: bytes):
        return self.hot_storage.get(expr_id)


def _ref_expr(hash_bytes: bytes) -> Expr:
    return link(bytes_(hash_bytes), symbol("ref"))


class TestRefOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_ref_empty_stack_returns_nil(self):
        expr, _ = parse(tokenize("(ref)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_ref_zero32_returns_nil(self):
        expr, _ = parse(tokenize("(0x0000000000000000000000000000000000000000000000000000000000000000 ref)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_ref_non_bytes_returns_nil(self):
        expr, _ = parse(tokenize('("not-a-hash" ref)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_ref_short_bytes_returns_nil(self):
        expr, _ = parse(tokenize("(0xdead ref)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_ref_no_node_returns_nil(self):
        h = "01" * 32
        expr, _ = parse(tokenize(f"(0x{h} ref)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_ref_resolves_symbol(self):
        stored = symbol("hello")
        h = stored.hash()
        node = FakeNode()
        node.hot_storage[h] = stored
        machine = Machine(node=node)
        expr = _ref_expr(h)
        result = machine.run(expr=expr)
        self.assertEqual(result._tag, "symbol")
        self.assertEqual(result.value, "hello")

    def test_ref_meter_link_fixed_70(self):
        stored = link(bytes_(b"\x01"), bytes_(b"\x02"))
        h = stored.hash()
        node = FakeNode()
        node.hot_storage[h] = stored
        machine = Machine(node=node, meter_limit=10_000)
        expr = _ref_expr(h)
        machine.run(expr=expr)
        self.assertEqual(machine.meter.total, 70 + 32)

    def test_ref_meter_bytes_sized(self):
        stored = bytes_(b"\x01\x02\x03")
        h = stored.hash()
        node = FakeNode()
        node.hot_storage[h] = stored
        machine = Machine(node=node, meter_limit=10_000)
        expr = _ref_expr(h)
        machine.run(expr=expr)
        self.assertEqual(machine.meter.total, stored.size() + 32)

    def test_ref_deterministic(self):
        stored = bytes_(b"\x01\x02\x03")
        h = stored.hash()
        node = FakeNode()
        node.hot_storage[h] = stored
        machine = Machine(node=node, mode="deterministic")
        expr = _ref_expr(h)
        result = machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_ref_zero32_ok(self):
        expr, _ = parse(tokenize("(0x0000000000000000000000000000000000000000000000000000000000000000 ref?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "link")
        self.assertIsNone(result._head._head)
        self.assertIsNone(result._head._tail)

    def test_ref_non_bytes_err(self):
        expr, _ = parse(tokenize('("not-a-hash" ref?)'))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "ref requires 32-byte hash, got str")

    def test_ref_short_bytes_err(self):
        expr, _ = parse(tokenize("(0xdead ref?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "ref requires 32-byte hash, got 2 bytes")

    def test_ref_no_node_err(self):
        h = "01" * 32
        expr, _ = parse(tokenize(f"(0x{h} ref?)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "ref requires a node connection")


if __name__ == "__main__":
    unittest.main(verbosity=2)
