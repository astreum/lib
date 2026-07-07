"""Validation tests for the CHANNEL_UPDATE (0x10) transaction code.

Prerequisites: an existing channel from sender to counterparty; tx recipient
must equal sender (self-update). Payload is counterparty(32) optionally
followed by a new withdrawal_window(8).
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
from astreum.consensus.transaction.channel.model import Channel
from astreum.consensus.transaction.code import TransactionCode
from astreum.machine.models.expression import ZERO32, resolve_inner_exprs
from astreum.consensus.models.receipt import STATUS_FAILED, STATUS_SUCCESS

from _helpers import (
    FAR_FUTURE_WINDOW,
    _FakeNode,
    flush_pending,
    make_block,
    make_previous_block,
    make_tx,
    seed_burn_account,
    seed_channel,
    seed_sender_account,
    store_tx,
)

RECIPIENT_SIZE = 32
WINDOW_SIZE = 8


class TestChannelUpdate(unittest.TestCase):
    def setUp(self):
        self.node = _FakeNode()
        self.prev_block = make_previous_block(timestamp=0)
        self.block = make_block(self.node, self.prev_block)
        seed_burn_account(self.block)

    def _get_channel(self, account, counterparty):
        head = account.channels.get(self.node, counterparty)
        return Channel.from_storage(self.node, head)

    # --- success ---

    def test_update_adds_balance_and_increments_counter(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        sender_acct = self.block.accounts.get_account(sender_pk, self.node)
        counterparty = os.urandom(32)
        seed_channel(
            self.node, sender_acct, counterparty,
            balance=500, counter=3, withdrawal_window=FAR_FUTURE_WINDOW,
        )
        self.block.accounts.set_account(sender_pk, sender_acct)

        payload = counterparty  # keep current window
        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=sender_pk,
            amount=200, code=TransactionCode.CHANNEL_UPDATE,
            data=payload, private_key=sender_key,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        flush_pending(self.node, self.block)

        receipt = self.block.receipts[-1]
        sender = self.block.accounts.get_account(sender_pk, self.node)
        ch = self._get_channel(sender, counterparty)
        self.assertEqual(receipt.status, STATUS_SUCCESS)
        self.assertEqual(ch.balance, 700)
        self.assertEqual(ch.counter, 4)
        self.assertEqual(ch.withdrawal_window, FAR_FUTURE_WINDOW)

    def test_update_extends_withdrawal_window(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        sender_acct = self.block.accounts.get_account(sender_pk, self.node)
        counterparty = os.urandom(32)
        current_window = 1000
        seed_channel(
            self.node, sender_acct, counterparty,
            balance=100, counter=1, withdrawal_window=current_window,
        )
        self.block.accounts.set_account(sender_pk, sender_acct)

        new_window = 5000
        payload = counterparty + new_window.to_bytes(8, "little")
        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=sender_pk,
            amount=0, code=TransactionCode.CHANNEL_UPDATE,
            data=payload, private_key=sender_key,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        flush_pending(self.node, self.block)

        receipt = self.block.receipts[-1]
        sender = self.block.accounts.get_account(sender_pk, self.node)
        ch = self._get_channel(sender, counterparty)
        self.assertEqual(receipt.status, STATUS_SUCCESS)
        self.assertEqual(ch.withdrawal_window, new_window)

    # --- failures ---

    def test_recipient_not_self_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        sender_acct = self.block.accounts.get_account(sender_pk, self.node)
        counterparty = os.urandom(32)
        seed_channel(
            self.node, sender_acct, counterparty,
            balance=500, counter=3, withdrawal_window=FAR_FUTURE_WINDOW,
        )
        self.block.accounts.set_account(sender_pk, sender_acct)

        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=os.urandom(32),
            amount=200, code=TransactionCode.CHANNEL_UPDATE,
            data=counterparty, private_key=sender_key,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        self.assertEqual(self.block.receipts[-1].status, STATUS_FAILED)

    def test_no_existing_channel_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        counterparty = os.urandom(32)

        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=sender_pk,
            amount=200, code=TransactionCode.CHANNEL_UPDATE,
            data=counterparty, private_key=sender_key,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        self.assertEqual(self.block.receipts[-1].status, STATUS_FAILED)

    def test_malformed_payload_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        sender_acct = self.block.accounts.get_account(sender_pk, self.node)
        counterparty = os.urandom(32)
        seed_channel(
            self.node, sender_acct, counterparty,
            balance=500, counter=3, withdrawal_window=FAR_FUTURE_WINDOW,
        )
        self.block.accounts.set_account(sender_pk, sender_acct)

        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=sender_pk,
            amount=200, code=TransactionCode.CHANNEL_UPDATE,
            data=b"too-short", private_key=sender_key,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        self.assertEqual(self.block.receipts[-1].status, STATUS_FAILED)

    def test_shortening_window_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        sender_acct = self.block.accounts.get_account(sender_pk, self.node)
        counterparty = os.urandom(32)
        current_window = 5000
        seed_channel(
            self.node, sender_acct, counterparty,
            balance=100, counter=1, withdrawal_window=current_window,
        )
        self.block.accounts.set_account(sender_pk, sender_acct)

        shorter = (1000).to_bytes(8, "little")
        payload = counterparty + shorter
        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=sender_pk,
            amount=0, code=TransactionCode.CHANNEL_UPDATE,
            data=payload, private_key=sender_key,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        self.assertEqual(self.block.receipts[-1].status, STATUS_FAILED)


if __name__ == "__main__":
    unittest.main()
