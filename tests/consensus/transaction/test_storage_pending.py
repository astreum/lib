"""Tests for pending storage contract lifecycle: slotting, overwrites, refunds."""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
HELPERS_DIR = Path(__file__).resolve().parent.parent / "validation"
if str(HELPERS_DIR) not in sys.path:
    sys.path.insert(0, str(HELPERS_DIR))

from astreum.consensus.transaction.storage.initial import generate_initial_storage_record
from astreum.consensus.transaction.storage.pending import (
    add_pending_storage_contract,
    finalize_pending_storage_contract,
)
from astreum.storage.radix import (
    get_from_radix_tree,
    get_radix_node_expr,
    put_in_radix_tree,
)
from astreum.storage.radix.node import radix_node_hash
from astreum.expression import Expr, NIL, int_, bytes_, link
from astreum.consensus.constants import STORAGE_ADDRESS

from _helpers import (
    _FakeNode,
    flush_pending,
    make_block,
    make_previous_block,
    seed_storage_account,
    store_expr_tree,
)


class TestGenerateInitialStorageRecord(unittest.TestCase):
    """Tests for _slot_if_new duplicate detection via generate_initial_storage_record."""

    def setUp(self):
        self.node = _FakeNode()
        self.prev_block = make_previous_block()
        self.block = make_block(self.node, self.prev_block)
        seed_storage_account(self.block)

    def test_duplicate_subexpr_within_tree_skipped(self):
        """Same atom appearing twice in a tree → slotted once, no gap in sequence."""
        x = int_(42)
        tree = link(x, link(x, NIL))
        store_expr_tree(self.node, tree)

        result = generate_initial_storage_record(self.node, self.block, tree)
        self.assertIsNotNone(result)
        record, slot_map, found_exprs, fee = result

        # x, link(x, nil), nil = 3 unique exprs (second x silently skipped)
        self.assertEqual(len(slot_map), 3)
        # No gaps in sequence numbers (the pre-fix bug produced 1,2,3 instead of 0,1,2)
        sequences = sorted(s.sequence for s in slot_map.values())
        self.assertEqual(sequences, [0, 1, 2])

    def test_subexpr_in_global_storage_goes_to_found(self):
        """Expr already in global radix tree → in found_exprs, not slotted."""
        pre_existing = int_(42)
        new_atom = int_(7)
        tree = link(pre_existing, link(new_atom, NIL))
        store_expr_tree(self.node, tree)

        # Pre-seed the atom in the storage radix tree
        storage_account = self.block.accounts.get_account(STORAGE_ADDRESS, self.node)
        put_in_radix_tree(storage_account.data, self.node, pre_existing.hash(), pre_existing)
        for tn in storage_account.data.nodes.values():
            self.node.hot_storage[radix_node_hash(tn)] = get_radix_node_expr(tn)
        storage_account.data_hash = storage_account.data.root_hash or b""

        result = generate_initial_storage_record(self.node, self.block, tree)
        self.assertIsNotNone(result)
        record, slot_map, found_exprs, fee = result

        self.assertIn(pre_existing.hash(), found_exprs)
        self.assertNotIn(new_atom.hash(), found_exprs)

    def test_all_unique_subexprs_slotted_sequentially(self):
        """Every unique sub-expr gets a sequential slot; found_exprs is empty."""
        a = int_(1)
        b = int_(2)
        c = int_(3)
        tree = link(a, link(b, link(c, NIL)))
        store_expr_tree(self.node, tree)

        result = generate_initial_storage_record(self.node, self.block, tree)
        self.assertIsNotNone(result)
        record, slot_map, found_exprs, fee = result

        self.assertEqual(len(found_exprs), 0)
        sequences = sorted(s.sequence for s in slot_map.values())
        self.assertEqual(sequences, list(range(len(slot_map))))


class TestPendingStorageRefunds(unittest.TestCase):
    """Tests for add_pending_storage_contract / finalize_pending_storage_contract."""

    def setUp(self):
        self.node = _FakeNode()
        self.prev_block = make_previous_block()
        self.block = make_block(self.node, self.prev_block)
        seed_storage_account(self.block)

    def _add_contract(
        self,
        value: Expr,
        destination: bytes | None = None,
        key: bytes | None = None,
    ) -> int:
        store_expr_tree(self.node, value)
        fee = add_pending_storage_contract(
            self.node, self.block, destination, key, value,
        )
        self.assertIsNotNone(fee)
        return fee

    def _contract_and_slot_count(self, value: Expr) -> int:
        """Return how many entries (1 record + N slots) a value would produce."""
        store_expr_tree(self.node, value)
        result = generate_initial_storage_record(self.node, self.block, value)
        self.assertIsNotNone(result)
        return 1 + len(result[1])  # record + slots

    def test_single_contract_survives(self):
        """One contract for a key → survives, no deletes or refunds."""
        value = link(int_(1), NIL)
        self._add_contract(value, b"dest", b"key")

        contracts, deletes, refunds = finalize_pending_storage_contract(self.node, self.block)

        self.assertGreater(len(contracts), 0)
        self.assertEqual(len(deletes), 0)
        self.assertEqual(len(refunds), 0)

    def test_overwrite_disjoint_exprs_full_refund(self):
        """Two contracts for the same key with disjoint exprs → first fully refunded."""
        value_a = link(int_(1), NIL)
        value_b = link(int_(2), NIL)
        fee_a = self._add_contract(value_a, b"dest", b"key")
        self._add_contract(value_b, b"dest", b"key")
        self.assertGreater(fee_a, 0)

        contracts, deletes, refunds = finalize_pending_storage_contract(self.node, self.block)

        # B (the winner) survives, A is fully deleted + refunded
        expected_b_count = self._contract_and_slot_count(value_b)
        self.assertEqual(len(contracts), expected_b_count)
        expected_a_count = self._contract_and_slot_count(value_a)
        self.assertEqual(len(deletes), expected_a_count)
        self.assertEqual(len(refunds), 1)
        self.assertEqual(refunds[0][1], fee_a)

    def test_oneshot_no_grouping(self):
        """key=None contracts are one-shot — both survive, no grouping."""
        value_a = link(int_(1), NIL)
        value_b = link(int_(2), NIL)
        self._add_contract(value_a, b"dest", None)
        self._add_contract(value_b, b"dest", None)

        contracts, deletes, refunds = finalize_pending_storage_contract(self.node, self.block)

        expected_total = (
            self._contract_and_slot_count(value_a)
            + self._contract_and_slot_count(value_b)
        )
        self.assertEqual(len(contracts), expected_total)
        self.assertEqual(len(deletes), 0)
        self.assertEqual(len(refunds), 0)

    def test_overwrite_with_shared_global_expr(self):
        """Two contracts sharing an expr already in global storage → full refund."""
        shared = int_(99)
        # Pre-seed shared expr in global storage
        storage_account = self.block.accounts.get_account(STORAGE_ADDRESS, self.node)
        put_in_radix_tree(storage_account.data, self.node, shared.hash(), shared)
        for tn in storage_account.data.nodes.values():
            self.node.hot_storage[radix_node_hash(tn)] = get_radix_node_expr(tn)
        storage_account.data_hash = storage_account.data.root_hash or b""

        value_a = link(shared, int_(1))
        value_b = link(shared, int_(2))
        fee_a = self._add_contract(value_a, b"dest", b"key")
        self._add_contract(value_b, b"dest", b"key")

        contracts, deletes, refunds = finalize_pending_storage_contract(self.node, self.block)

        # A gets full refund; its record + 1 slot deleted
        self.assertEqual(len(refunds), 1)
        self.assertEqual(refunds[0][1], fee_a)
        expected_a = self._contract_and_slot_count(link(shared, int_(1)))
        self.assertEqual(len(deletes), expected_a)

        # B's contracts = 1 record + 1 slot (shared is found, only int_(2) slotted)
        self.assertEqual(len(contracts), 2)


if __name__ == "__main__":
    unittest.main()
