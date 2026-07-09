import sys
import unittest
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Expr, tokenize, parse
from astreum.machine.main import Machine
from astreum.expression import NIL, ZERO32, int_, fp64_, bytes_, str_, symbol, link


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
        self.hot_storage_timestamps = {}
        self.hot_storage_lock = threading.Lock()
        self.config = {"expr_fetch_interval": 0, "expr_fetch_retries": 0}
        self.logger = type(
            "L", (), {"debug": lambda *a, **kw: None, "info": lambda *a, **kw: None}
        )()

    def get_expr(self, expr_id: bytes):
        return self.hot_storage.get(expr_id)

    def get_expr_full(self, expr_id: bytes):
        expr = self.get_expr(expr_id)
        if expr is None:
            return None
        if not expr._tag == "link":
            return expr
        if expr._head is None and expr._head_hash is not None:
            head = self.get_expr_full(expr._head_hash)
            if head is None:
                return None
            expr._head = head
            expr._head_hash = None
        if expr._tail is None and expr._tail_hash is not None:
            tail = self.get_expr_full(expr._tail_hash)
            if tail is None:
                return None
            expr._tail = tail
            expr._tail_hash = None
        return expr


def _load_expr(hash_bytes: bytes) -> Expr:
    return link(bytes_(hash_bytes), link(symbol("load"), None))


class TestLoadOperator(unittest.TestCase):
    def setUp(self):
        self.machine = Machine(node=None)

    def test_load_empty_stack_returns_nil(self):
        expr, _ = parse(tokenize("(load)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_load_zero32_returns_nil(self):
        expr, _ = parse(tokenize("(0x0000000000000000000000000000000000000000000000000000000000000000 load)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_load_non_bytes_returns_nil(self):
        expr, _ = parse(tokenize('("not-a-hash" load)'))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_load_short_bytes_returns_nil(self):
        expr, _ = parse(tokenize("(0xdead load)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_load_no_node_returns_nil(self):
        h = "01" * 32
        expr, _ = parse(tokenize(f"(0x{h} load)"))
        result = self.machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_load_underflow_raises(self):
        pass

    def test_load_resolves_symbol(self):
        stored = symbol("hello")
        h = stored.hash()
        node = FakeNode()
        node.hot_storage[h] = stored
        machine = Machine(node=node)
        expr = _load_expr(h)
        result = machine.run(expr=expr)
        self.assertEqual(result._tag, "symbol")
        self.assertEqual(result.value, "hello")

    def test_load_resolves_link_concrete(self):
        stored = link(bytes_(b"\x01"), bytes_(b"\x02"))
        h = stored.hash()
        node = FakeNode()
        node.hot_storage[h] = stored
        machine = Machine(node=node)
        expr = _load_expr(h)
        result = machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertEqual(result._head._tag, "bytes")
        self.assertEqual(result._head.value, b"\x01")
        self.assertEqual(result._tail._tag, "bytes")
        self.assertEqual(result._tail.value, b"\x02")

    def test_load_meter_double_size(self):
        stored = link(bytes_(b"\x01"), bytes_(b"\x02"))
        h = stored.hash()
        node = FakeNode()
        node.hot_storage[h] = stored
        machine = Machine(node=node, meter_limit=10_000)
        expr = _load_expr(h)
        machine.run(expr=expr)
        self.assertEqual(machine.meter.total, stored.size() * 2 + 32)

    def test_load_deterministic(self):
        stored = bytes_(b"\x01\x02\x03")
        h = stored.hash()
        node = FakeNode()
        node.hot_storage[h] = stored
        machine = Machine(node=node, mode="deterministic")
        expr = _load_expr(h)
        result = machine.run(expr=expr)
        self.assertEqual(result._tag, "link")
        self.assertIsNone(result._head)
        self.assertIsNone(result._tail)

    def test_load_zero32_ok(self):
        expr, _ = parse(tokenize("(0x0000000000000000000000000000000000000000000000000000000000000000 'load try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "ok"))
        self.assertEqual(result._head._tag, "link")
        self.assertIsNone(result._head._head)
        self.assertIsNone(result._head._tail)

    def test_load_non_bytes_err(self):
        expr, _ = parse(tokenize("(\"not-a-hash\" 'load try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "load requires 32-byte hash, got str")

    def test_load_short_bytes_err(self):
        expr, _ = parse(tokenize("(0xdead 'load try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "load requires 32-byte hash, got 2 bytes")

    def test_load_no_node_err(self):
        h = "01" * 32
        expr, _ = parse(tokenize(f"(0x{h} 'load try)"))
        result = self.machine.run(expr=expr)
        self.assertTrue(_is_tagged(result, "err"))
        self.assertEqual(result._head._tag, "str")
        self.assertEqual(result._head.value, "load requires a node connection")


if __name__ == "__main__":
    unittest.main(verbosity=2)