import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, "src")

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from astreum.consensus.transaction.code import TransactionCode
from astreum.storage.workers.claim import _build_multi_claim_tx, _next_claim_counter


def _make_keys():
    secret = ed25519.Ed25519PrivateKey.generate()
    public = secret.public_key()
    return secret, public


def _public_bytes(public):
    return public.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


class _AccountsStub:
    def __init__(self, account=None, raises=False):
        self.account = account
        self.raises = raises

    def get_account(self, address=None, node=None):
        if self.raises:
            raise RuntimeError("trie fetch failed")
        return self.account


def _make_node(storage_public_key_bytes, accounts, chain_id=1):
    node = SimpleNamespace(
        config={"chain_id": chain_id},
        storage_public_key_bytes=storage_public_key_bytes,
        storage_secret_key=None,
        latest_block=SimpleNamespace(accounts=accounts),
        logger=SimpleNamespace(info=lambda *a, **k: None, exception=lambda *a, **k: None),
    )
    return node


class TestNextClaimCounter(unittest.TestCase):
    def setUp(self):
        self.secret, self.public = _make_keys()
        self.pk = _public_bytes(self.public)

    def test_on_chain_counter_used(self):
        account = SimpleNamespace(counter=7)
        node = _make_node(self.pk, _AccountsStub(account=account))
        self.assertEqual(_next_claim_counter(node), 7)

    def test_local_wins_when_ahead(self):
        account = SimpleNamespace(counter=3)
        node = _make_node(self.pk, _AccountsStub(account=account))
        node.next_claim_counter = 4
        self.assertEqual(_next_claim_counter(node), 4)

    def test_on_chain_wins_when_ahead(self):
        account = SimpleNamespace(counter=9)
        node = _make_node(self.pk, _AccountsStub(account=account))
        node.next_claim_counter = 2
        self.assertEqual(_next_claim_counter(node), 9)

    def test_missing_account_is_zero(self):
        node = _make_node(self.pk, _AccountsStub(account=None))
        self.assertEqual(_next_claim_counter(node), 0)

    def test_fetch_failure_falls_back_to_local(self):
        node = _make_node(self.pk, _AccountsStub(raises=True))
        node.next_claim_counter = 5
        self.assertEqual(_next_claim_counter(node), 5)

    def test_fetch_failure_without_local_is_zero(self):
        node = _make_node(self.pk, _AccountsStub(raises=True))
        self.assertEqual(_next_claim_counter(node), 0)

    def test_no_latest_block_is_zero(self):
        node = _make_node(self.pk, _AccountsStub(account=SimpleNamespace(counter=6)))
        node.latest_block = None
        self.assertEqual(_next_claim_counter(node), 0)


class TestBuildMultiClaimTx(unittest.TestCase):
    def setUp(self):
        self.secret, self.public = _make_keys()
        self.pk = _public_bytes(self.public)
        self.node = _make_node(self.pk, _AccountsStub())
        self.node.storage_secret_key = self.secret

    def test_uses_given_counter(self):
        tx = _build_multi_claim_tx(self.node, [(b"a" * 32, b"b" * 32, 42)], self.secret, 11)
        self.assertEqual(tx.counter, 11)

    def test_signed_and_well_formed(self):
        tx = _build_multi_claim_tx(self.node, [(b"a" * 32, b"b" * 32, 42)], self.secret, 0)
        self.assertEqual(tx.code, TransactionCode.STORAGE_PAYMENT)
        self.assertEqual(tx.sender, self.pk)
        self.assertTrue(tx.signature)
        self.assertEqual(tx.recipient, b"\x00" * 32)

    def test_consecutive_counters(self):
        tx1 = _build_multi_claim_tx(self.node, [(b"a" * 32, b"b" * 32, 1)], self.secret, 3)
        tx2 = _build_multi_claim_tx(self.node, [(b"a" * 32, b"b" * 32, 2)], self.secret, 4)
        self.assertEqual((tx1.counter, tx2.counter), (3, 4))
        self.assertNotEqual(tx1.expr().hash(), tx2.expr().hash())


if __name__ == "__main__":
    unittest.main()
