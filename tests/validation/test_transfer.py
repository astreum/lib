"""Validation tests for the TRANSFER (0x00) transaction code."""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
HELPERS_DIR = Path(__file__).resolve().parent
if str(HELPERS_DIR) not in sys.path:
    sys.path.insert(0, str(HELPERS_DIR))

from astreum.consensus.transaction import apply_transaction
from astreum.consensus.transaction.code import TransactionCode
from astreum.validation.constants import BURN_ADDRESS
from astreum.validation.models.receipt import STATUS_FAILED, STATUS_SUCCESS

from _helpers import (
    _FakeNode,
    make_block,
    make_previous_block,
    make_tx,
    seed_burn_account,
    seed_sender_account,
    store_tx,
)


class TestTransfer(unittest.TestCase):
    def setUp(self):
        self.node = _FakeNode()
        self.prev_block = make_previous_block()
        self.block = make_block(self.node, self.prev_block)
        seed_burn_account(self.block)

    # --- success ---

    def test_transfer_moves_balance_and_succeeds(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        recipient = os.urandom(32)
        amount = 100_000

        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=recipient,
            amount=amount, private_key=sender_key,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)

        receipt = self.block.receipts[-1]
        sender = self.block.accounts.get_account(sender_pk, self.node)
        recipient_acct = self.block.accounts.get_account(recipient, self.node)

        self.assertEqual(receipt.status, STATUS_SUCCESS)
        self.assertEqual(recipient_acct.balance, amount)
        self.assertEqual(
            sender.balance,
            1_000_000 - amount - receipt.transaction_fee - receipt.storage_fee,
        )

    def test_transfer_to_self_only_pays_fees(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=sender_pk,
            amount=5000, private_key=sender_key,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)

        receipt = self.block.receipts[-1]
        sender = self.block.accounts.get_account(sender_pk, self.node)
        self.assertEqual(receipt.status, STATUS_SUCCESS)
        self.assertEqual(
            sender.balance,
            1_000_000 - receipt.transaction_fee - receipt.storage_fee,
        )

    def test_transfer_appended_with_correct_attributes(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        recipient = os.urandom(32)
        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=recipient,
            amount=777, private_key=sender_key,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)

        self.assertEqual(len(self.block.transactions), 1)
        self.assertEqual(len(self.block.receipts), 1)
        self.assertEqual(self.block.transactions[0].hash, tx_hash)
        self.assertEqual(self.block.receipts[0].transaction_hash, tx_hash)
        self.assertEqual(self.block.transactions[0].code, TransactionCode.TRANSFER)

    # --- failures ---

    def test_chain_id_mismatch_raises(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        tx = make_tx(
            chain_id=99, sender_pk=sender_pk, recipient=os.urandom(32),
            amount=100, private_key=sender_key,
        )
        tx_hash = store_tx(self.node, tx)

        with self.assertRaises(ValueError):
            apply_transaction(self.node, self.block, tx_hash)

    def test_insufficient_balance_for_fee_raises(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=0)
        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=os.urandom(32),
            amount=1, private_key=sender_key,
        )
        tx_hash = store_tx(self.node, tx)

        with self.assertRaises(ValueError):
            apply_transaction(self.node, self.block, tx_hash)

    def test_insufficient_balance_for_amount_fails_receipt(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1)
        recipient = os.urandom(32)
        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=recipient,
            amount=100_000, private_key=sender_key,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)

        receipt = self.block.receipts[-1]
        recipient_acct = self.block.accounts.get_account(recipient, self.node)
        self.assertEqual(receipt.status, STATUS_FAILED)
        self.assertEqual(recipient_acct.balance, 0)


if __name__ == "__main__":
    unittest.main()
