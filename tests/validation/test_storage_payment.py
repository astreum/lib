"""Validation tests for the STORAGE_PAYMENT (0x31) transaction code.

A storage-payment rewards the sender for hosting atom data by proving
continued availability via a challenge-response PoW mechanism.
"""

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

from blake3 import blake3

from astreum.consensus.transaction import apply_transaction
from astreum.consensus.transaction.code import TransactionCode
from astreum.consensus.transaction.model import Transaction
from astreum.consensus.transaction.storage.model import StorageRecord
from astreum.consensus.account import create_account
from astreum.consensus.transaction.storage.payment import (
    _leading_zero_bits,
    _required_bits,
)
from astreum.machine.models.expression import Expr, ZERO32
from astreum.validation.constants import BURN_ADDRESS
from astreum.validation.models.receipt import STATUS_FAILED, STATUS_SUCCESS

from _helpers import (
    _FakeNode,
    flush_pending,
    make_block,
    make_previous_block,
    seed_burn_account,
    seed_expr_list,
    seed_sender_account,
    store_expr_tree,
    store_tx,
)


class TestStoragePayment(unittest.TestCase):
    def setUp(self):
        self.node = _FakeNode()
        self.prev_block = make_previous_block()
        self.block = make_block(self.node, self.prev_block)
        seed_burn_account(self.block)
        store_expr_tree(self.node, self.prev_block.expr())

    def _seed_storage_record(
        self,
        atom_list_id: bytes,
        last_payment_block_hash: bytes | None = None,
        new_size: int = 1000,
        new_count: int = 5,
    ) -> None:
        """Insert a StorageRecord into burn_account.data under atom_list_id."""
        burn = self.block.accounts.get_account(BURN_ADDRESS, self.node)
        lbh = last_payment_block_hash or self.prev_block.expr().hash()
        record = StorageRecord(
            creation_block_hash=lbh,
            last_payment_block_hash=lbh,
            last_payment_winner=ZERO32,
            new_size=new_size,
            new_count=new_count,
        )
        record_head = store_expr_tree(self.node, record.expr())
        burn.data.put(self.node, atom_list_id, record_head)
        for tn in burn.data.nodes.values():
            self.node.hot_storage[tn.hash()] = tn.expr()
        burn.data_hash = burn.data.root_hash or ZERO32

    # ------------------------------------------------------------------
    # Success
    # ------------------------------------------------------------------

    def test_successful_payment(self):
        data_items = [Expr.Bytes(os.urandom(100)) for _ in range(5)]
        atom_list_id = seed_expr_list(self.node, data_items)

        sender = atom_list_id  # sender == list_id → required_bits = 0
        self.block.accounts.set_account(sender, create_account(balance=1_000_000))

        lbh = self.prev_block.expr().hash()
        self._seed_storage_record(
            atom_list_id=atom_list_id,
            last_payment_block_hash=lbh,
            new_size=1000,
            new_count=len(data_items),
        )

        challenge_seed = blake3(lbh + atom_list_id).digest()
        challenge_index = (
            int.from_bytes(challenge_seed[:8], "little", signed=False)
            % len(data_items)
        )
        challenged_data = data_items[challenge_index]
        challenge_data_hash = blake3(challenged_data.value).digest()

        nonce = b"\x00" * 64
        payload = atom_list_id + nonce + challenge_data_hash

        tx = Transaction(
            chain_id=1,
            amount=0,
            code=TransactionCode.STORAGE_PAYMENT,
            counter=1,
            cost_limit=0,
            data=payload,
            recipient=BURN_ADDRESS,
            sender=sender,
        )
        tx_hash = store_tx(self.node, tx)

        block_mint_before = self.block.total_mint

        apply_transaction(self.node, self.block, tx_hash)
        flush_pending(self.node, self.block)

        receipt = self.block.receipts[-1]
        self.assertEqual(receipt.status, STATUS_SUCCESS)

        expected_payout = 1000 * (self.block.height - 0)
        self.assertEqual(self.block.total_mint, block_mint_before + expected_payout)

        burn = self.block.accounts.get_account(BURN_ADDRESS, self.node)
        updated_head = burn.data.get(self.node, atom_list_id)
        self.assertIsNotNone(updated_head)
        updated = StorageRecord.from_storage(self.node, updated_head)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.last_payment_winner, bytes(sender))
        self.assertEqual(updated.last_payment_block_hash,
                         self.block.previous_block_hash)

    # ------------------------------------------------------------------
    # Failures — payload / parsing
    # ------------------------------------------------------------------

    def test_wrong_payload_size_short_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        payload = b"\x00" * 10  # too short
        tx = Transaction(
            chain_id=1,
            amount=0,
            code=TransactionCode.STORAGE_PAYMENT,
            counter=1,
            cost_limit=0,
            data=payload,
            recipient=BURN_ADDRESS,
            sender=sender_pk,
        )
        tx_hash = store_tx(self.node, tx)
        apply_transaction(self.node, self.block, tx_hash)
        self.assertEqual(self.block.receipts[-1].status, STATUS_FAILED)

    def test_wrong_payload_size_long_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        payload = b"\x00" * 200  # too long (not PAYLOAD_SIZE or PAYLOAD_WITH_FLAG_SIZE)
        tx = Transaction(
            chain_id=1,
            amount=0,
            code=TransactionCode.STORAGE_PAYMENT,
            counter=1,
            cost_limit=0,
            data=payload,
            recipient=BURN_ADDRESS,
            sender=sender_pk,
        )
        tx_hash = store_tx(self.node, tx)
        apply_transaction(self.node, self.block, tx_hash)
        self.assertEqual(self.block.receipts[-1].status, STATUS_FAILED)

    def test_wrong_flag_bit_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        data_items = [Expr.Bytes(b"x")]
        atom_list_id = seed_expr_list(self.node, data_items)
        # flag != 1 → _parse_payload returns None
        payload = b"\x00" + atom_list_id + b"\x00" * 64 + blake3(b"x").digest()
        tx = Transaction(
            chain_id=1,
            amount=0,
            code=TransactionCode.STORAGE_PAYMENT,
            counter=1,
            cost_limit=0,
            data=payload,
            recipient=BURN_ADDRESS,
            sender=sender_pk,
        )
        tx_hash = store_tx(self.node, tx)
        apply_transaction(self.node, self.block, tx_hash)
        self.assertEqual(self.block.receipts[-1].status, STATUS_FAILED)

    # ------------------------------------------------------------------
    # Failures — no contract / bad record
    # ------------------------------------------------------------------

    def test_no_contract_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        missing_id = os.urandom(32)
        payload = missing_id + b"\x00" * 64 + b"\x00" * 32
        tx = Transaction(
            chain_id=1,
            amount=0,
            code=TransactionCode.STORAGE_PAYMENT,
            counter=1,
            cost_limit=0,
            data=payload,
            recipient=BURN_ADDRESS,
            sender=sender_pk,
        )
        tx_hash = store_tx(self.node, tx)
        apply_transaction(self.node, self.block, tx_hash)
        self.assertEqual(self.block.receipts[-1].status, STATUS_FAILED)

    def test_zero_atom_count_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        data_items = [Expr.Bytes(b"data")]
        atom_list_id = seed_expr_list(self.node, data_items)
        self._seed_storage_record(
            atom_list_id=atom_list_id,
            new_count=0,
            new_size=100,
        )
        payload = atom_list_id + b"\x00" * 64 + b"\x00" * 32
        tx = Transaction(
            chain_id=1,
            amount=0,
            code=TransactionCode.STORAGE_PAYMENT,
            counter=1,
            cost_limit=0,
            data=payload,
            recipient=BURN_ADDRESS,
            sender=sender_pk,
        )
        tx_hash = store_tx(self.node, tx)
        apply_transaction(self.node, self.block, tx_hash)
        self.assertEqual(self.block.receipts[-1].status, STATUS_FAILED)

    def test_zero_byte_size_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        data_items = [Expr.Bytes(b"data")]
        atom_list_id = seed_expr_list(self.node, data_items)
        self._seed_storage_record(
            atom_list_id=atom_list_id,
            new_count=1,
            new_size=0,
        )
        payload = atom_list_id + b"\x00" * 64 + b"\x00" * 32
        tx = Transaction(
            chain_id=1,
            amount=0,
            code=TransactionCode.STORAGE_PAYMENT,
            counter=1,
            cost_limit=0,
            data=payload,
            recipient=BURN_ADDRESS,
            sender=sender_pk,
        )
        tx_hash = store_tx(self.node, tx)
        apply_transaction(self.node, self.block, tx_hash)
        self.assertEqual(self.block.receipts[-1].status, STATUS_FAILED)

    # ------------------------------------------------------------------
    # Failures — PoW / challenge
    # ------------------------------------------------------------------

    def test_insufficient_pow_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        data_items = [Expr.Bytes(b"data")]
        atom_list_id = seed_expr_list(self.node, data_items)
        lbh = self.prev_block.expr().hash()
        self._seed_storage_record(
            atom_list_id=atom_list_id,
            last_payment_block_hash=lbh,
            new_count=1,
            new_size=1000,
        )
        challenge_data_hash = blake3(b"data").digest()
        # Use a nonce that deliberately fails the PoW
        nonce = b"\x00" * 64
        required = _required_bits(provider_key=sender_pk, atom_list_id=atom_list_id)
        work = blake3(lbh + sender_pk + atom_list_id + challenge_data_hash + nonce).digest()
        if _leading_zero_bits(work) >= required:
            self.skipTest("nonce accidentally passed PoW — skip")

        payload = atom_list_id + nonce + challenge_data_hash
        tx = Transaction(
            chain_id=1,
            amount=0,
            code=TransactionCode.STORAGE_PAYMENT,
            counter=1,
            cost_limit=0,
            data=payload,
            recipient=BURN_ADDRESS,
            sender=sender_pk,
        )
        tx_hash = store_tx(self.node, tx)
        apply_transaction(self.node, self.block, tx_hash)
        self.assertEqual(self.block.receipts[-1].status, STATUS_FAILED)

    def test_bad_challenge_data_hash_fails(self):
        data_items = [Expr.Bytes(b"real-data")]
        atom_list_id = seed_expr_list(self.node, data_items)

        sender = atom_list_id  # required_bits = 0
        self.block.accounts.set_account(sender, create_account(balance=1_000_000))

        lbh = self.prev_block.expr().hash()
        self._seed_storage_record(
            atom_list_id=atom_list_id,
            last_payment_block_hash=lbh,
            new_count=1,
            new_size=1000,
        )
        challenge_data_hash = blake3(b"wrong-data").digest()
        nonce = b"\x00" * 64
        payload = atom_list_id + nonce + challenge_data_hash
        tx = Transaction(
            chain_id=1,
            amount=0,
            code=TransactionCode.STORAGE_PAYMENT,
            counter=1,
            cost_limit=0,
            data=payload,
            recipient=BURN_ADDRESS,
            sender=sender,
        )
        tx_hash = store_tx(self.node, tx)
        apply_transaction(self.node, self.block, tx_hash)
        self.assertEqual(self.block.receipts[-1].status, STATUS_FAILED)

    # ------------------------------------------------------------------
    # Failures — invalid tx properties
    # ------------------------------------------------------------------

    def test_wrong_recipient_succeeds_without_payment(self):
        """Recipient != BURN_ADDRESS → handler skipped, receipt stays SUCCESS."""
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        other = os.urandom(32)
        data_items = [Expr.Bytes(b"data")]
        atom_list_id = seed_expr_list(self.node, data_items)
        self._seed_storage_record(
            atom_list_id=atom_list_id,
            new_count=1,
            new_size=100,
        )
        payload = atom_list_id + b"\x00" * 64 + b"\x00" * 32
        tx = Transaction(
            chain_id=1,
            amount=0,
            code=TransactionCode.STORAGE_PAYMENT,
            counter=1,
            cost_limit=0,
            data=payload,
            recipient=other,
            sender=sender_pk,
        )
        tx_hash = store_tx(self.node, tx)
        apply_transaction(self.node, self.block, tx_hash)
        # Receipt succeeds because the handler isn't called for non-burn recipients
        self.assertEqual(self.block.receipts[-1].status, STATUS_SUCCESS)

    def test_non_zero_amount_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        data_items = [Expr.Bytes(b"data")]
        atom_list_id = seed_expr_list(self.node, data_items)
        self._seed_storage_record(
            atom_list_id=atom_list_id,
            new_count=1,
            new_size=100,
        )
        payload = atom_list_id + b"\x00" * 64 + b"\x00" * 32
        tx = Transaction(
            chain_id=1,
            amount=100,
            code=TransactionCode.STORAGE_PAYMENT,
            counter=1,
            cost_limit=0,
            data=payload,
            recipient=BURN_ADDRESS,
            sender=sender_pk,
        )
        tx_hash = store_tx(self.node, tx)
        apply_transaction(self.node, self.block, tx_hash)
        self.assertEqual(self.block.receipts[-1].status, STATUS_FAILED)


if __name__ == "__main__":
    unittest.main()
