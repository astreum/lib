import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, "src")

from astreum.expression import Expr, NIL, ZERO32, bytes_, int_
from astreum.expression import RESOLUTION_SINGLE
from astreum.consensus.transaction.storage.model import StorageRecord, StorageSlot
from astreum.storage.get.list.cold import list_exprs_in_cold_storage
from astreum.storage.put.cold.insert import put_expr_in_cold_storage
from astreum.storage.put.cold.collate import collate_exprs
from astreum.storage.radix import RadixTree, put_in_radix_tree
from astreum.storage.workers.claim import _build_inverse_view, _run_cold_recovery
from astreum.node import Node


def _make_node(cold_path: str) -> Node:
    node = Node(
        {
            "cold_storage_path": cold_path,
            "cold_storage_scale": "KB",
            "cold_storage_base_size": 10 * 1024 * 1024,
            "default_seed": None,
            "verbose": False,
        }
    )
    node.storage_public_key_bytes = b"\x02" * 32
    return node


def _store_expr(node: Node, expr: Expr) -> bytes:
    expr_id = expr.hash()
    stored = put_expr_in_cold_storage(node, expr)
    assert stored, f"failed to store expr {expr_id.hex()}"
    return expr_id


class TestListExprsInColdStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.node = _make_node(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_empty_cold_storage(self):
        self.assertEqual(list_exprs_in_cold_storage(self.node), [])

    def test_level_0_only(self):
        ids = {_store_expr(self.node, bytes_(f"v{i}".encode())) for i in range(3)}
        self.assertEqual(set(list_exprs_in_cold_storage(self.node)), ids)

    def test_collated_level_1(self):
        exprs = [bytes_(f"v{i}".encode()) for i in range(3)]
        ids = {e.hash() for e in exprs}
        for e in exprs:
            _store_expr(self.node, e)
        self.assertTrue(collate_exprs(Path(self.node.config["cold_storage_path"])))
        fresh_id = _store_expr(self.node, bytes_(b"fresh"))
        self.assertEqual(
            set(list_exprs_in_cold_storage(self.node)), ids | {fresh_id}
        )

    def test_dedup_across_levels(self):
        e = bytes_(b"dup")
        _store_expr(self.node, e)
        self.assertTrue(collate_exprs(Path(self.node.config["cold_storage_path"])))
        _store_expr(self.node, e)
        ids = list_exprs_in_cold_storage(self.node)
        self.assertEqual(ids.count(e.hash()), 1)


class TestColdBootRecovery(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.node = _make_node(self.temp_dir.name)

        self.record = StorageRecord(
            creation_block_hash=ZERO32,
            last_payment_block_hash=ZERO32,
            last_payment_height=5000,
            last_payment_winner=b"\x01" * 32,
            new_size=100,
            new_count=1,
            mint=False,
        )
        self.record_id = self.record.expr().hash()
        self.slot = StorageSlot(record_hash=self.record_id, sequence=0)
        self.slot_id = self.slot.expr().hash()

        self.tree = RadixTree()
        put_in_radix_tree(self.tree, self.node, self.slot_id, self.slot.expr())
        put_in_radix_tree(self.tree, self.node, self.record_id, self.record.expr())

        from astreum.consensus.models.accounts import _trie_nodes_exprs

        for e in _trie_nodes_exprs(self.tree):
            _store_expr(self.node, e)
        self.orphan = bytes_(b"orphan")
        _store_expr(self.node, self.orphan)

        storage_account = SimpleNamespace(data=self.tree)
        self.block = SimpleNamespace(
            height=5000,
            accounts=SimpleNamespace(
                get_account=lambda address, node=None: storage_account
            ),
        )
        self.node.latest_block = self.block

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_recovery_rebuilds_registry_and_adverts(self):
        self.node.storage_index[b"\x99" * 32] = 12345

        _run_cold_recovery(self.node)

        self.assertEqual(
            self.node.storage_slot_registry, {self.slot_id: (self.record_id, 0)}
        )
        self.assertEqual(self.node.storage_records_held, {self.record_id})
        self.assertEqual(self.node.claim_spacing_eras, {self.record_id: 4})

        advert_ids = {entry[0] for entry in self.node.expr_advertisements}
        self.assertEqual(advert_ids, {self.slot_id, self.record_id})
        for entry in self.node.expr_advertisements:
            self.assertEqual(entry[1], RESOLUTION_SINGLE)

        self.assertEqual(self.node.storage_index, {b"\x99" * 32: 12345})

    def test_orphan_skipped_but_retained(self):
        _run_cold_recovery(self.node)

        self.assertEqual(self.node.storage_records_held, {self.record_id})
        ids = list_exprs_in_cold_storage(self.node)
        self.assertIn(self.orphan.hash(), ids)

    def test_recovery_without_cold_data(self):
        with tempfile.TemporaryDirectory() as empty_dir:
            node = _make_node(empty_dir)
            node.latest_block = self.block
            self.assertEqual(_run_cold_recovery(node), -1)
            self.assertEqual(node.storage_slot_registry, {})
            self.assertEqual(node.storage_records_held, set())

    def test_inverse_view_from_registry(self):
        node = self.node
        node.storage_slot_registry = {
            b"\x01" * 32: (b"\xaa" * 32, 0),
            b"\x02" * 32: (b"\xaa" * 32, 1),
            b"\x03" * 32: (b"\xbb" * 32, 3),
        }
        inverse = _build_inverse_view(node)
        self.assertEqual(
            inverse[b"\xaa" * 32], {0: b"\x01" * 32, 1: b"\x02" * 32}
        )
        self.assertEqual(inverse[b"\xbb" * 32], {3: b"\x03" * 32})
        self.assertNotIn(b"\xcc" * 32, inverse)


if __name__ == "__main__":
    unittest.main()