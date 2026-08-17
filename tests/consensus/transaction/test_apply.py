"""Tests for apply_transaction with a minimal in-memory storage node."""

import sys
import unittest
import os
import threading
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.consensus.transaction import apply_transaction
from astreum.consensus.transaction.model import Transaction
from astreum.consensus.transaction.code import TransactionCode
from astreum.consensus.transaction.storage.contract import calculate_transaction_costs
from astreum.consensus.account import create_account
from astreum.consensus.models.block import Block
from astreum.consensus.block.create import create_block
from astreum.consensus.models.accounts import Accounts
from astreum.consensus.models.receipt import STATUS_SUCCESS, STATUS_FAILED
from astreum.consensus.constants import STORAGE_ADDRESS, TREASURY_ADDRESS
from astreum.expression import Expr, NIL, ZERO32, bytes_
from astreum.storage.radix import RadixTree
from astreum.consensus.block.encoding.expr import get_block_expr
from astreum.crypto.bloom_tree import BloomTree


class _FakeNode:
    """Minimal in-memory storage node for testing."""

    def __init__(self):
        self.hot_storage: dict[bytes, Expr] = {}
        self.hot_storage_lock = threading.Lock()
        self.hot_storage_timestamps: dict[bytes, float] = {}
        self.hot_storage_size = 0
        self.config = {"hot_storage_limit": 10 * 1024 * 1024}
        self.logger = type(
            "FakeLogger",
            (),
            {
                "debug": lambda *a, **kw: None,
                "info": lambda *a, **kw: None,
                "warning": lambda *a, **kw: None,
                "exception": lambda *a, **kw: None,
            },
        )()

    def get_expr(self, expr_id: bytes) -> Expr | None:
        return self.hot_storage.get(expr_id)

    def get_expr_list(self, root_hash: bytes) -> Expr | None:
        return self.hot_storage.get(root_hash)


def _make_tx(
    *,
    chain_id: int,
    sender_pk: bytes,
    recipient: bytes,
    amount: int,
    code: TransactionCode = TransactionCode.TRANSFER,
    data: Expr = NIL,
    secret_key,
    cost_limit: int = 0,
    counter: int = 0,
) -> Transaction:
    if isinstance(data, bytes):
        data = bytes_(data)
    tx = Transaction(
        chain_id=chain_id,
        amount=amount,
        code=code,
        counter=counter,
        cost_limit=cost_limit,
        data=data,
        recipient=recipient,
        sender=sender_pk,
    )
    tx.sign(secret_key)
    return tx


def _store_tx(node: _FakeNode, tx: Transaction) -> bytes:
    """Store a transaction's expr tree in fake node and return its hash."""
    expr = tx.expr()
    tx_hash = expr.hash()
    node.hot_storage[tx_hash] = expr
    return tx_hash


def _make_previous_block() -> Block:
    """Create a minimal previous block with positive cumulative values."""
    return create_block(
        chain_id=1,
        previous_block_hash=ZERO32,
        previous_block=None,
        height=0,
        timestamp=0,
        accounts_hash=ZERO32,
        total_transaction_fee=0,
        total_storage_fee=0,
        statistics=[(1, 1, 0, 0)],
        transactions_hash=ZERO32,
        receipts_hash=ZERO32,
        difficulty=1,
        validator_public_key_bytes=os.urandom(32),
    )


def _make_block(
    node: _FakeNode, prev_block: Block, *, chain_id: int = 1, height: int = 1
) -> Block:
    block = create_block(
        chain_id=chain_id,
        previous_block_hash=get_block_expr(prev_block).hash(),
        previous_block=prev_block,
        height=1,
        timestamp=0,
        accounts_hash=ZERO32,
        total_transaction_fee=0,
        total_storage_fee=0,
        transactions_hash=ZERO32,
        receipts_hash=ZERO32,
        difficulty=1,
        validator_public_key_bytes=os.urandom(32),
    )
    block.accounts = Accounts()
    block.transactions = []
    block.receipts = []
    block.bloom_tree = BloomTree()
    return block


def _seed_sender_account(block: Block, balance: int = 10_000_000) -> bytes:
    """Create and cache a sender account, return its public key."""
    key = Ed25519PrivateKey.generate()
    pk = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    block.accounts.set_account(pk, create_account(balance=balance))
    return pk, key


def _seed_storage_account(block: Block) -> None:
    """Seed the storage account with an empty data trie (root_hash=None)."""
    from astreum.consensus.account import Account

    storage_account = Account(
        balance=0,
        code_hash=ZERO32,
        counter=0,
        data_hash=ZERO32,
        channels_hash=ZERO32,
        data=RadixTree(root_hash=None),
        channels=RadixTree(root_hash=None),
    )
    block.accounts.set_account(STORAGE_ADDRESS, storage_account)


class TestApplyTransaction(unittest.TestCase):

    def setUp(self):
        self.node = _FakeNode()
        self.prev_block = _make_previous_block()
        self.block = _make_block(self.node, self.prev_block)
        _seed_storage_account(self.block)

    def test_simple_transfer_updates_balances(self):
        """A TRANSFER transaction moves balance from sender to recipient."""
        sender_pk, sender_key = _seed_sender_account(self.block, balance=1_000_000)
        recipient = os.urandom(32)
        amount = 100_000

        tx = _make_tx(
            chain_id=1,
            sender_pk=sender_pk,
            recipient=recipient,
            amount=amount,
            secret_key=sender_key,
        )
        tx_hash = _store_tx(self.node, tx)

        apply_transaction(
            self.node, self.block, tx_hash
        )

        receipt = self.block.receipts[-1]
        tx_fee = receipt.transaction_fee
        storage_fee = receipt.storage_fee
        total_fee = receipt.total_fee
        mandatory_storage_cost = calculate_transaction_costs(
            block=self.block, transaction=tx
        )

        # Sender lost: tx_fee + transfer_amount + mandatory_storage_cost
        sender = self.block.accounts.get_account(sender_pk, self.node)
        recipient_account = self.block.accounts.get_account(recipient, self.node)

        self.assertIsNotNone(sender)
        self.assertIsNotNone(recipient_account)
        self.assertEqual(recipient_account.balance, amount)
        self.assertEqual(
            sender.balance,
            1_000_000 - amount - receipt.transaction_fee - receipt.storage_fee,
        )

    def test_insufficient_balance_raises(self):
        """Transaction with balance < tx_fee raises ValueError."""
        sender_pk, sender_key = _seed_sender_account(self.block, balance=0)
        tx = _make_tx(
            chain_id=1,
            sender_pk=sender_pk,
            recipient=os.urandom(32),
            amount=1,
            secret_key=sender_key,
        )
        tx_hash = _store_tx(self.node, tx)

        with self.assertRaises(ValueError):
            apply_transaction(self.node, self.block, tx_hash)

    def test_appends_transaction_and_receipt(self):
        """After apply, block.transactions and block.receipts grow by one."""
        sender_pk, sender_key = _seed_sender_account(self.block, balance=1_000_000)
        tx = _make_tx(
            chain_id=1,
            sender_pk=sender_pk,
            recipient=os.urandom(32),
            amount=100,
            secret_key=sender_key,
        )
        tx_hash = _store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)

        self.assertEqual(len(self.block.transactions), 1)
        self.assertEqual(len(self.block.receipts), 1)
        self.assertEqual(self.block.transactions[0].hash, tx_hash)
        self.assertEqual(
            self.block.receipts[0].transaction_hash, tx_hash
        )

    def test_receipt_status_success(self):
        """A valid TRANSFER yields receipt status STATUS_SUCCESS."""
        sender_pk, sender_key = _seed_sender_account(self.block, balance=1_000_000)
        tx = _make_tx(
            chain_id=1,
            sender_pk=sender_pk,
            recipient=os.urandom(32),
            amount=100,
            secret_key=sender_key,
        )
        tx_hash = _store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)

        self.assertEqual(self.block.receipts[0].status, STATUS_SUCCESS)

    def test_chain_id_mismatch_raises(self):
        """A transaction with different chain_id than the block raises."""
        sender_pk, sender_key = _seed_sender_account(self.block, balance=1_000_000)
        tx = _make_tx(
            chain_id=99,  # mismatched
            sender_pk=sender_pk,
            recipient=os.urandom(32),
            amount=100,
            secret_key=sender_key,
        )
        tx_hash = _store_tx(self.node, tx)

        with self.assertRaises(ValueError):
            apply_transaction(self.node, self.block, tx_hash)

    def test_burn_account_receives_storage_fee(self):
        """The STORAGE_ADDRESS balance increases by mandatory_storage_cost."""
        sender_pk, sender_key = _seed_sender_account(self.block, balance=1_000_000)
        tx = _make_tx(
            chain_id=1,
            sender_pk=sender_pk,
            recipient=os.urandom(32),
            amount=100,
            secret_key=sender_key,
        )
        tx_hash = _store_tx(self.node, tx)
        burn_before = self.block.accounts.get_account(
            STORAGE_ADDRESS, self.node
        ).balance

        apply_transaction(self.node, self.block, tx_hash)
        burn_after = self.block.accounts.get_account(
            STORAGE_ADDRESS, self.node
        ).balance
        # Burn receives mandatory_storage_cost at bottom of apply_transaction
        self.assertGreater(burn_after, burn_before)

    def test_transfer_to_self(self):
        """Sending to yourself just pays fees, no net balance change."""
        sender_pk, sender_key = _seed_sender_account(self.block, balance=1_000_000)
        amount = 5000

        tx = _make_tx(
            chain_id=1,
            sender_pk=sender_pk,  # recipient = sender
            recipient=sender_pk,
            amount=amount,
            secret_key=sender_key,
        )
        tx_hash = _store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        receipt = self.block.receipts[-1]
        tx_fee = receipt.transaction_fee
        storage_fee = receipt.storage_fee

        sender = self.block.accounts.get_account(sender_pk, self.node)
        mandatory_storage_cost = calculate_transaction_costs(
            block=self.block, transaction=tx
        )
        # Balance unchanged since sender == recipient (amount cancels out),
        # but fees are still deducted
        self.assertEqual(
            sender.balance,
            1_000_000 - receipt.transaction_fee - receipt.storage_fee,
        )

    def test_tx_stored_in_block_transactions_has_attributes(self):
        """The transaction object appended to the block is complete."""
        sender_pk, sender_key = _seed_sender_account(self.block, balance=1_000_000)
        recipient = os.urandom(32)
        tx = _make_tx(
            chain_id=1,
            sender_pk=sender_pk,
            recipient=recipient,
            amount=777,
            secret_key=sender_key,
        )
        tx_hash = _store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)

        stored_tx = self.block.transactions[0]
        self.assertEqual(stored_tx.sender, sender_pk)
        self.assertEqual(stored_tx.recipient, recipient)
        self.assertEqual(stored_tx.amount, 777)
        self.assertEqual(stored_tx.code, TransactionCode.TRANSFER)


class TestApplyTransactionFailureReceipt(unittest.TestCase):
    """Tests for transactions that produce a FAILED receipt, not an exception."""

    def setUp(self):
        self.node = _FakeNode()
        self.prev_block = _make_previous_block()
        self.block = _make_block(self.node, self.prev_block)
        _seed_storage_account(self.block)

    def test_send_to_burn_with_amount_fails(self):
        """Sending amount > 0 to STORAGE_ADDRESS with STORAGE_CREATE code fails."""
        sender_pk, sender_key = _seed_sender_account(self.block, balance=1_000_000)
        tx = _make_tx(
            chain_id=1,
            sender_pk=sender_pk,
            recipient=STORAGE_ADDRESS,
            amount=1000,
            code=TransactionCode.STORAGE_CREATE,
            secret_key=sender_key,
        )
        tx_hash = _store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        receipt = self.block.receipts[-1]
        tx_fee = receipt.transaction_fee
        storage_fee = receipt.storage_fee

        self.assertEqual(self.block.receipts[0].status, STATUS_FAILED)
        # Sender still pays fees even on failure
        sender = self.block.accounts.get_account(sender_pk, self.node)
        mandatory_storage_cost = calculate_transaction_costs(
            block=self.block, transaction=tx
        )
        self.assertEqual(
            sender.balance,
            1_000_000 - receipt.transaction_fee - receipt.storage_fee,
        )


if __name__ == "__main__":
    unittest.main()
