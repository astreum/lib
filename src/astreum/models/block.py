from __future__ import annotations

from typing import List, Dict, Any, Optional, Union

from astreum.models.account import Account
from astreum.models.accounts import Accounts
from astreum.models.patricia import PatriciaTrie
from astreum.models.transaction import Transaction
from ..crypto import ed25519
from .merkle import MerkleTree

# Constants for integer field names
_INT_FIELDS = {
    "delay_difficulty",
    "number",
    "timestamp",
    "transaction_limit",
    "transactions_total_fees",
}

class Block:
    def __init__(
        self,
        block_hash: bytes,
        *,
        number: Optional[int] = None,
        prev_block_hash: Optional[bytes] = None,
        timestamp: Optional[int] = None,
        accounts_hash: Optional[bytes] = None,
        accounts: Optional[Accounts] = None,
        transaction_limit: Optional[int] = None,
        transactions_total_fees: Optional[int] = None,
        transactions_root_hash: Optional[bytes] = None,
        transactions_count: Optional[int] = None,
        delay_difficulty: Optional[int] = None,
        delay_output: Optional[bytes] = None,
        delay_proof: Optional[bytes] = None,
        validator_pk: Optional[bytes] = None,
        body_tree: Optional[MerkleTree] = None,
        signature: Optional[bytes] = None,
    ):
        self.hash = block_hash
        self.number = number
        self.prev_block_hash = prev_block_hash
        self.timestamp = timestamp
        self.accounts_hash = accounts_hash
        self.accounts = accounts
        self.transaction_limit = transaction_limit
        self.transactions_total_fees = transactions_total_fees
        self.transactions_root_hash = transactions_root_hash
        self.transactions_count = transactions_count
        self.delay_difficulty = delay_difficulty
        self.delay_output = delay_output
        self.delay_proof = delay_proof
        self.validator_pk = validator_pk
        self.body_tree = body_tree
        self.signature = signature

    @property
    def hash(self) -> bytes:
        return self._block_hash

    def get_body_hash(self) -> bytes:
        """Return the Merkle root of the body fields."""
        if not self._body_tree:
            raise ValueError("Body tree not available for this block instance.")
        return self._body_tree.root_hash

    def get_signature(self) -> bytes:
        """Return the block's signature leaf."""
        if self._signature is None:
            raise ValueError("Signature not available for this block instance.")
        return self._signature

    def get_field(self, name: str) -> Union[int, bytes]:
        """Query a single body field by name, returning an int or bytes."""
        if name not in self._field_names:
            raise KeyError(f"Unknown field: {name}")
        if not self._body_tree:
            raise ValueError("Body tree not available for field queries.")
        idx = self._field_names.index(name)
        leaf_bytes = self._body_tree.leaves[idx]
        if name in _INT_FIELDS:
            return int.from_bytes(leaf_bytes, "big")
        return leaf_bytes

    def verify_block_signature(self) -> bool:
        """Verify the block's Ed25519 signature against its body root."""
        pub = ed25519.Ed25519PublicKey.from_public_bytes(
            self.get_field("validator_pk")
        )
        try:
            pub.verify(self.get_signature(), self.get_body_hash())
            return True
        except Exception:
            return False

    @classmethod
    def genesis(cls, validator_addr: bytes) -> "Block":
        # 1 . validator-stakes sub-trie
        stake_trie = PatriciaTrie()
        stake_trie.put(validator_addr, (1).to_bytes(32, "big"))
        stake_root = stake_trie.root_hash

        # 2 . build the two Account bodies
        validator_acct = Account.create(balance=0, data=b"",        nonce=0)
        treasury_acct  = Account.create(balance=1, data=stake_root, nonce=0)

        # 3 . global Accounts structure
        accts = Accounts()
        accts.set_account(validator_addr, validator_acct)
        accts.set_account(b"\x11" * 32, treasury_acct)
        accounts_hash = accts.root_hash

        # 4 . constant body fields for genesis
        body_kwargs = dict(
            number                  = 0,
            prev_block_hash         = b"\x00" * 32,
            timestamp               = 0,
            accounts_hash           = accounts_hash,
            transactions_total_fees = 0,
            transaction_limit       = 0,
            transactions_root_hash  = b"\x00" * 32,
            delay_difficulty        = 0,
            delay_output            = b"",
            delay_proof             = b"",
            validator_pk            = validator_addr,
            signature               = b"",
        )

        # 5 . build and return the block
        return cls.create(**body_kwargs)

    @classmethod
    def build(
        cls,
        previous_block: "Block",
        transactions: List[Transaction],
        *,
        validator_pk: bytes,
        natural_rate: float = 0.618,  # threshold factor (~61.8%)
    ) -> "Block":
        """Deterministic block-construction routine.

        * State updates go through :py:meth:`Accounts.set_account` exclusively.
        * 50 %% of total fees are burned (address 0x00…00), 50 %% paid to *validator_pk*.
        * Sending to the treasury (0x11…11) is a stake deposit: update stake-trie stored
          in the treasury account's *data* field.
        * The per-block *transaction_limit* has a minimum floor of 1, and then
          grows or shrinks each block according to *natural_rate* based on
          **previous block transaction count** and **previous limit**:
          - GROW when *prev_tx_count* > *prev_limit* × *natural_rate* → new limit = *prev_tx_count*.
          - SHRINK when *prev_tx_count* < *prev_limit* × *natural_rate* → new limit = max(1,⌊*prev_limit* × *natural_rate*⌋).
          - Otherwise, the limit remains *prev_limit*.
        """

        TREASURY = b"\x11" * 32
        BURN     = b"\x00" * 32

        # 1. load previous state and metrics
        accts         = Accounts(root_hash=previous_block.get_field("accounts_hash"))
        prev_limit    = previous_block.get_field("transaction_limit")
        prev_stamp    = previous_block.get_field("timestamp")
        prev_tx_count = previous_block.get_field("transactions_count")
        total_fees    = 0

        # 2. cap the number of processed txs by floor(prev_limit,1)
        floor_limit   = max(prev_limit, 1)
        effective_txs = transactions[:floor_limit]

        # helper: credit balances via Accounts
        def _credit(addr: bytes, amount: int) -> None:
            acc = accts.get_account(addr)
            bal = acc.balance() if acc else 0
            dat = acc.data()    if acc else b""
            nce = acc.nonce()   if acc else 0
            accts.set_account(addr, Account.create(balance=bal + amount, data=dat, nonce=nce))

        # 3. process transactions and accumulate fees
        for tx in effective_txs:
            sender    = tx.get_sender_pk()
            recipient = tx.get_recipient_pk()
            amount    = tx.get_amount()
            fee       = tx.get_fee()
            nonce     = tx.get_nonce()

            snd_acc = accts.get_account(sender)
            if snd_acc is None or snd_acc.nonce() != nonce or snd_acc.balance() < amount + fee:
                raise ValueError("invalid transaction")

            # debit sender
            accts.set_account(
                sender,
                Account.create(
                    balance=snd_acc.balance() - amount - fee,
                    data=snd_acc.data(),
                    nonce=snd_acc.nonce() + 1,
                ),
            )

            # handle stake deposit or regular transfer
            if recipient == TREASURY:
                treasury = accts.get_account(TREASURY)
                trie     = PatriciaTrie(node_get=None, root_hash=treasury.data())
                curr     = int.from_bytes(trie.get(sender) or b"", "big")
                trie.put(sender, (curr + amount).to_bytes(32, "big"))
                accts.set_account(
                    TREASURY,
                    Account.create(
                        balance=treasury.balance() + amount,
                        data=trie.root_hash,
                        nonce=treasury.nonce(),
                    ),
                )
            elif recipient != BURN:
                rcpt = accts.get_account(recipient)
                rbal = rcpt.balance() if rcpt else 0
                rdat = rcpt.data()    if rcpt else b""
                rnon = rcpt.nonce()   if rcpt else 0
                accts.set_account(
                    recipient,
                    Account.create(balance=rbal + amount, data=rdat, nonce=rnon),
                )

            # accumulate fee (split in step 4)
            total_fees += fee

        # 4. distribute fees: burn and reward validator
        burn_amt = total_fees // 2
        reward_amt = total_fees - burn_amt
        if burn_amt:
            _credit(BURN, burn_amt)
        if reward_amt:
            _credit(validator_pk, reward_amt)

        # 5. adjust transaction_limit via natural_rate using prev metrics
        threshold = prev_limit * natural_rate
        if prev_tx_count > threshold:
            new_limit = prev_tx_count
        elif prev_tx_count < threshold:
            new_limit = max(1, int(prev_limit * natural_rate))
        else:
            new_limit = prev_limit

        # 6. merkle root of processed transactions
        tx_root = MerkleTree.from_leaves([tx.hash for tx in effective_txs]).root_hash

        # 7. assemble block body (including new count) and return
        body = dict(
            number                  = previous_block.get_field("number") + 1,
            prev_block_hash         = previous_block.hash,
            timestamp               = prev_stamp + 1,
            accounts_hash           = accts.root_hash,
            transactions_total_fees = total_fees,
            transaction_limit       = new_limit,
            transactions_root_hash  = tx_root,
            transactions_count      = len(effective_txs),
            delay_difficulty        = previous_block.get_field("delay_difficulty"),
            delay_output            = b"",
            delay_proof             = b"",
            validator_pk            = validator_pk,
            signature               = b"",
        )

        return cls.create(**body)