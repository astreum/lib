"""Tests for validator queue processing.

These tests verify that a validator node enqueues a signed transaction via
``enqueue_transaction_hash`` and the validation worker picks it up from its
own ``_validation_transaction_queue`` (the *process their own queue only*
property — there is no shared mempool).
"""

import sys
import socket
import time
import unittest
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.node import Node
from astreum.consensus.transaction import Transaction, TransactionCode
from astreum.consensus.account import create_account
from astreum.machine.models.expression import resolve_inner_exprs, ZERO32
from astreum.validation.genesis import create_genesis_block
from astreum.validation.models.accounts import extract_accounts_exprs


class TestValidationQueue(unittest.TestCase):

    @staticmethod
    def _get_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def test_validator_sends_funds_via_own_queue(self) -> None:
        """Validator enqueues a TRANSFER tx → worker includes it in the next
        block, confirming that the local per-node queue is the mechanism by
        which transactions reach the block producer."""
        port = self._get_free_port()
        node = Node(config={
            "incoming_port": port,
            "default_seed": None,
            "additional_seeds": [],
            "storage_index_interval": 1,
            "atom_fetch_interval": 1,
            "verbose": False,
        })
        try:
            secret_key = Ed25519PrivateKey.generate()
            validator_pk = secret_key.public_key().public_bytes(
                Encoding.Raw, PublicFormat.Raw,
            )

            # --- custom genesis with a pre-funded validator ----------------
            genesis = create_genesis_block(node, validator_pk, chain_id=0)

            validator_account = genesis.accounts.get_account(validator_pk, node)
            validator_account.balance = 1_000_000
            genesis.accounts.set_account(validator_pk, validator_account)

            # Inflate cumulative_transaction_fee so the storage-fee
            # denominator keeps storage fees near zero.
            genesis.cumulative_transaction_fee = 10_000_000
            genesis.accounts_hash = (
                genesis.accounts.update_trie(node) or ZERO32
            )

            for expr in resolve_inner_exprs(node, genesis.expr())[0]:
                node._hot_storage_set(expr)
            for expr in extract_accounts_exprs(genesis.accounts):
                node._hot_storage_set(expr)

            node.latest_block_hash = genesis.expr().hash()
            node.latest_block = genesis

            # --- build the transfer tx ------------------------------------
            recipient = os.urandom(32)
            tx = Transaction(
                chain_id=node.config["chain_id"],
                amount=1,
                code=TransactionCode.TRANSFER,
                counter=0,
                recipient=recipient,
                sender=validator_pk,
            )
            tx.sign(secret_key)
            tx_hash = tx.expr().hash()

            tx_exprs, missed = resolve_inner_exprs(node, tx.expr())
            self.assertEqual(missed, [])
            for expr in tx_exprs:
                node._hot_storage_set(expr)

            # --- start validation & enqueue --------------------------------
            node.validate(secret_key)
            node.enqueue_transaction_hash(tx_hash)

            # --- wait for a block that includes our transaction ------------
            deadline = time.time() + 25
            while time.time() < deadline:
                current = node.latest_block
                if current is not None and current.transactions:
                    if any(t.hash == tx_hash for t in current.transactions):
                        break
                time.sleep(0.1)
            else:
                self.fail(
                    "transaction was not included in any block within timeout"
                )

            # --- verify the receipt ---------------------------------------
            latest = node.latest_block
            receipt = latest.receipts[0]
            self.assertEqual(receipt.transaction_hash, tx_hash)

            # The queue should have been drained by the worker.
            self.assertTrue(
                node._validation_transaction_queue.empty(),
                "the worker should have drained the queue",
            )

        finally:
            node.disconnect()


if __name__ == "__main__":
    unittest.main()
