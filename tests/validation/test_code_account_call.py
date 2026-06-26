"""Validation tests for the CODE_ACCOUNT_CALL (0x41) transaction code."""

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

from astreum.consensus.account import create_account
from astreum.consensus.transaction import apply_transaction
from astreum.consensus.transaction.code import TransactionCode
from astreum.machine.models.expression import Expr, ZERO32
from astreum.machine.parser import parse
from astreum.machine.tokenizer import tokenize
from astreum.validation.constants import BURN_ADDRESS
from astreum.validation.models.receipt import STATUS_FAILED, STATUS_SUCCESS

from _helpers import (
    _FakeNode,
    flush_pending,
    make_block,
    make_previous_block,
    make_tx,
    seed_burn_account,
    seed_program,
    seed_sender_account,
    store_tx,
)


def _parse(program):
    expr, _ = parse(tokenize(program))
    return expr


class TestCodeAccountCall(unittest.TestCase):
    def setUp(self):
        self.node = _FakeNode()
        self.prev_block = make_previous_block()
        self.block = make_block(self.node, self.prev_block)
        seed_burn_account(self.block)

    def _seed_expression_account(self, program, *, balance=0):
        code_hash = seed_program(self.node, program)
        recipient = os.urandom(32)
        acct = create_account(balance=balance, code_hash=code_hash)
        self.block.accounts.set_account(recipient, acct)
        return recipient, acct

    # --- success ---

    def test_acc_balance_reads_balance(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        prog = _parse("(drop acc.balance)")
        recipient, _ = self._seed_expression_account(prog, balance=5000)

        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=recipient,
            amount=1000, code=TransactionCode.CODE_ACCOUNT_CALL,
            data=b"", private_key=sender_key, cost_limit=100,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        receipt = self.block.receipts[-1]
        self.assertEqual(receipt.status, STATUS_SUCCESS)
        self.assertGreater(receipt.transaction_fee, 0)

        acct = self.block.accounts.get_account(recipient, self.node)
        self.assertEqual(acct.balance, 6000)

    def test_acc_pay_transfers_to_sender(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        prog = _parse("(tx.sender 0x03e8 acc.pay)")
        recipient, _ = self._seed_expression_account(prog, balance=5000)

        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=recipient,
            amount=1000, code=TransactionCode.CODE_ACCOUNT_CALL,
            data=b"", private_key=sender_key, cost_limit=500,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        receipt = self.block.receipts[-1]
        self.assertEqual(receipt.status, STATUS_SUCCESS)

        sender = self.block.accounts.get_account(sender_pk, self.node)
        recipient_acct = self.block.accounts.get_account(recipient, self.node)
        self.assertEqual(recipient_acct.balance, 5000)
        self.assertGreater(sender.balance, 990_000)

    def test_acc_pay_to_new_account_creates_recipient(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=2_000_000)
        new_addr = os.urandom(32)
        prog = _parse("(0x" + new_addr.hex() + " 0x03e8 acc.pay)")
        recipient, _ = self._seed_expression_account(prog, balance=5000)

        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=recipient,
            amount=0, code=TransactionCode.CODE_ACCOUNT_CALL,
            data=b"", private_key=sender_key, cost_limit=500,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        flush_pending(self.node, self.block)
        receipt = self.block.receipts[-1]
        self.assertEqual(receipt.status, STATUS_SUCCESS)

        new_acct = self.block.accounts.get_account(new_addr, self.node)
        self.assertIsNotNone(new_acct)
        self.assertEqual(new_acct.balance, 1000)

        burn = self.block.accounts.get_account(BURN_ADDRESS, self.node)
        self.assertGreater(burn.balance, 0)

    def test_acc_get_reads_from_data_trie(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        key = b"\xde\xad\xbe\xef"
        value = b"\xca\xfe\xba\xbe"
        prog = _parse("(drop 0xdeadbeef acc.get)")
        recipient, acct = self._seed_expression_account(prog, balance=0)
        acct.data.put(self.node, key, value)
        acct.data_hash = acct.data.root_hash or ZERO32
        self.block.accounts.set_account(recipient, acct)

        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=recipient,
            amount=0, code=TransactionCode.CODE_ACCOUNT_CALL,
            data=b"", private_key=sender_key, cost_limit=100,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        receipt = self.block.receipts[-1]
        self.assertEqual(receipt.status, STATUS_SUCCESS)

    def test_acc_put_writes_to_data_trie(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=2_000_000)
        prog = _parse("(drop 0xdeadbeef 0xcafebabe acc.put)")
        recipient, _ = self._seed_expression_account(prog, balance=0)

        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=recipient,
            amount=0, code=TransactionCode.CODE_ACCOUNT_CALL,
            data=b"", private_key=sender_key, cost_limit=500,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        flush_pending(self.node, self.block)
        receipt = self.block.receipts[-1]
        self.assertEqual(receipt.status, STATUS_SUCCESS)

        acct = self.block.accounts.get_account(recipient, self.node)
        stored = acct.data.get(self.node, b"\xde\xad\xbe\xef")
        self.assertIsInstance(stored, Expr.Bytes)
        self.assertEqual(stored.value, b"\xca\xfe\xba\xbe")

        burn = self.block.accounts.get_account(BURN_ADDRESS, self.node)
        self.assertGreater(burn.balance, 0)

    # --- failures ---

    def test_acc_pay_insufficient_balance_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        prog = _parse("(tx.sender 0x7fffffff acc.pay)")
        recipient, _ = self._seed_expression_account(prog, balance=1000)

        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=recipient,
            amount=0, code=TransactionCode.CODE_ACCOUNT_CALL,
            data=b"", private_key=sender_key, cost_limit=500,
        )
        tx_hash = store_tx(self.node, tx)
        sender_before = self.block.accounts.get_account(sender_pk, self.node).balance
        recipient_before = self.block.accounts.get_account(recipient, self.node).balance

        apply_transaction(self.node, self.block, tx_hash)
        receipt = self.block.receipts[-1]
        self.assertEqual(receipt.status, STATUS_FAILED)

        sender_after = self.block.accounts.get_account(sender_pk, self.node).balance
        self.assertLess(sender_after, sender_before)
        recipient_after = self.block.accounts.get_account(recipient, self.node).balance
        self.assertEqual(recipient_after, recipient_before)

    def test_call_missing_recipient_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        missing = os.urandom(32)

        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=missing,
            amount=0, code=TransactionCode.CODE_ACCOUNT_CALL,
            data=b"", private_key=sender_key, cost_limit=100,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        receipt = self.block.receipts[-1]
        self.assertEqual(receipt.status, STATUS_FAILED)

    def test_call_zero_code_hash_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        recipient = os.urandom(32)
        acct = create_account(balance=0, code_hash=ZERO32)
        self.block.accounts.set_account(recipient, acct)

        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=recipient,
            amount=0, code=TransactionCode.CODE_ACCOUNT_CALL,
            data=b"", private_key=sender_key, cost_limit=100,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        receipt = self.block.receipts[-1]
        self.assertEqual(receipt.status, STATUS_FAILED)

    def test_call_program_not_in_storage_fails(self):
        sender_pk, sender_key = seed_sender_account(self.block, balance=1_000_000)
        recipient = os.urandom(32)
        fake_code_hash = os.urandom(32)
        acct = create_account(balance=0, code_hash=fake_code_hash)
        self.block.accounts.set_account(recipient, acct)

        tx = make_tx(
            chain_id=1, sender_pk=sender_pk, recipient=recipient,
            amount=0, code=TransactionCode.CODE_ACCOUNT_CALL,
            data=b"", private_key=sender_key, cost_limit=100,
        )
        tx_hash = store_tx(self.node, tx)

        apply_transaction(self.node, self.block, tx_hash)
        receipt = self.block.receipts[-1]
        self.assertEqual(receipt.status, STATUS_FAILED)


if __name__ == "__main__":
    unittest.main()
