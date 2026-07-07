"""Validation tests for the STORAGE_CREATE (0x30) transaction code.

A storage-create registers an expr list in the storage account's data trie under
its head hash, creating a StorageRecord. The recipient must be the
STORAGE_ADDRESS and amount must be 0 (amount > 0 is rejected).
"""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
HELPERS_DIR = Path(__file__).resolve().parent
if str(HELPERS_DIR) not in sys.path:
    sys.path.insert(0, str(HELPERS_DIR))

from astreum.consensus.transaction import apply_transaction
from astreum.consensus.transaction.code import TransactionCode
from astreum.consensus.transaction.storage.model import StorageRecord
from astreum.machine.models.expression import Expr, bytes_
from astreum.consensus.constants import STORAGE_ADDRESS
from astreum.consensus.models.receipt import STATUS_FAILED, STATUS_SUCCESS

from _helpers import (
    _FakeNode,
    flush_pending,
    make_block,
    make_previous_block,
    make_tx,
    seed_burn_account,
    seed_expr_list,
    seed_sender_account,
    store_tx,
)


class TestStorageCreate(unittest.TestCase):
    def setUp(self):
        self.node = _FakeNode()
        self.prev_block = make_previous_block()
        self.block = make_block(self.node, self.prev_block)
        seed_burn_account(self.block)

    # --- success ---

    def test_create_registers_storage_record(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        exprs = [bytes_(b"atom-alpha"), bytes_(b"atom-beta")]
        list_id = seed_expr_list(self.node, exprs)

        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=STORAGE_ADDRESS,
            amount=0, code=TransactionCode.STORAGE_CREATE,
            data=bytes_(list_id), private_key=sender_key,
        )
        tx_hash = store_tx(self.node, tx)
        balance_before = self.block.accounts.get_account(STORAGE_ADDRESS, self.node).balance

        apply_transaction(self.node, self.block, tx_hash)
        flush_pending(self.node, self.block)

        receipt = self.block.receipts[-1]
        storage_account = self.block.accounts.get_account(STORAGE_ADDRESS, self.node)
        self.assertEqual(receipt.status, STATUS_SUCCESS)

        record_head = storage_account.data.get(self.node, list_id)
        self.assertIsNotNone(record_head)
        record = StorageRecord.from_storage(self.node, record_head)
        self.assertIsNotNone(record)
        self.assertEqual(record.new_count, len(exprs))
        self.assertEqual(record.new_size, sum(e.size() for e in exprs))
        self.assertGreater(storage_account.balance, balance_before)  # storage fee charged

    # --- failures ---

    def test_recipient_not_burn_creates_no_record(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        exprs = [bytes_(b"atom-a")]
        list_id = seed_expr_list(self.node, exprs)
        other = os.urandom(32)

        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=other,
            amount=0, code=TransactionCode.STORAGE_CREATE,
            data=bytes_(list_id), private_key=sender_key,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        flush_pending(self.node, self.block)

        storage_account = self.block.accounts.get_account(STORAGE_ADDRESS, self.node)
        # recipient != STORAGE_ADDRESS → no record created under storage data
        self.assertIsNone(storage_account.data.get(self.node, list_id))

    def test_amount_to_burn_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        exprs = [bytes_(b"atom-a")]
        list_id = seed_expr_list(self.node, exprs)

        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=STORAGE_ADDRESS,
            amount=1000, code=TransactionCode.STORAGE_CREATE,
            data=bytes_(list_id), private_key=sender_key,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        self.assertEqual(self.block.receipts[-1].status, STATUS_FAILED)

    def test_already_registered_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        exprs = [bytes_(b"atom-a")]
        list_id = seed_expr_list(self.node, exprs)

        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=STORAGE_ADDRESS,
            amount=0, code=TransactionCode.STORAGE_CREATE,
            data=bytes_(list_id), private_key=sender_key,
        )
        tx_hash = store_tx(self.node, tx)

        # First create succeeds.
        apply_transaction(self.node, self.block, tx_hash)
        flush_pending(self.node, self.block)
        self.assertEqual(self.block.receipts[-1].status, STATUS_SUCCESS)

        # Second create for the same list_id fails (already registered).
        tx2 = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=STORAGE_ADDRESS,
            amount=0, code=TransactionCode.STORAGE_CREATE,
            data=bytes_(list_id), private_key=sender_key,
        )
        tx2_hash = store_tx(self.node, tx2)
        apply_transaction(self.node, self.block, tx2_hash)
        self.assertEqual(self.block.receipts[-1].status, STATUS_FAILED)

    def test_list_id_not_found_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        missing_id = os.urandom(32)  # not stored in node

        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=STORAGE_ADDRESS,
            amount=0, code=TransactionCode.STORAGE_CREATE,
            data=bytes_(missing_id), private_key=sender_key,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        self.assertEqual(self.block.receipts[-1].status, STATUS_FAILED)


if __name__ == "__main__":
    unittest.main()
