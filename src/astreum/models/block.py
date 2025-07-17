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
        transactions: list[Transaction],
        *,
        validator_pk: bytes,
        natural_rate: float = 0.618,
    ) -> "Block":
        BURN     = b"\x00" * 32

        # --- 0. create an empty block-in-progress, seeded with parent fields ----
        blk = cls(
            block_hash=b"",                         # placeholder; set at the end
            number=previous_block.number + 1,
            prev_block_hash=previous_block.hash,
            timestamp=previous_block.timestamp + 1,
            accounts_hash=previous_block.accounts_hash,
            transaction_limit=previous_block.transaction_limit,
            transactions_count=0,
        )

        # --- 1. apply up to transaction_limit txs -------------------------------
        for tx in transactions:
            try:
                blk.apply_tx(tx)                   # ← NEW single-line call
            except ValueError:
                break                              # stop at first invalid or cap reached

        # --- 2. split fees after all txs ----------------------------------------
        burn_amt   = blk.total_fees // 2
        reward_amt = blk.total_fees - burn_amt
        if burn_amt:
            blk.accounts.set_account(
                BURN,
                Account.create(
                    balance=(blk.accounts.get_account(BURN) or Account.create(0, b"", 0)).balance() + burn_amt,
                    data=b"",
                    nonce=0,
                ),
            )
        if reward_amt:
            blk.accounts.set_account(
                validator_pk,
                Account.create(
                    balance=(blk.accounts.get_account(validator_pk) or Account.create(0, b"", 0)).balance() + reward_amt,
                    data=b"",
                    nonce=0,
                ),
            )

        # --- 3. recalc tx-limit via prev metrics -------------------------------
        prev_limit    = previous_block.transaction_limit
        prev_tx_count = previous_block.transactions_count
        threshold     = prev_limit * natural_rate
        if prev_tx_count > threshold:
            blk.transaction_limit = prev_tx_count
        elif prev_tx_count < threshold:
            blk.transaction_limit = max(1, int(prev_limit * natural_rate))
        else:
            blk.transaction_limit = prev_limit

        # --- 4. finalise block hash & header roots ------------------------------
        blk.accounts_hash = blk.accounts.root_hash
        blk.transactions_root_hash = MerkleTree.from_leaves(blk.tx_hashes).root_hash
        blk.hash = MerkleTree.from_leaves([
            blk.transactions_root_hash,
            blk.accounts_hash,
            blk.total_fees.to_bytes(8, "big"),
        ]).root_hash  # or your existing body-root/signing scheme

        return blk

    
    def apply_tx(self, tx: Transaction) -> None:
        # --- lazy state ----------------------------------------------------
        if not hasattr(self, "accounts") or self.accounts is None:
            self.accounts = Accounts(root_hash=self.accounts_hash)
        if not hasattr(self, "total_fees"):
            self.total_fees = 0
            self.tx_hashes = []
            self.transactions_count = 0

        TREASURY = b"\x11" * 32
        BURN     = b"\x00" * 32

        # --- cap check -----------------------------------------------------
        if self.transactions_count >= self.transaction_limit:
            raise ValueError("block transaction limit reached")

        # --- unpack tx -----------------------------------------------------
        sender_pk  = tx.get_sender_pk()
        recip_pk   = tx.get_recipient_pk()
        amount     = tx.get_amount()
        fee        = tx.get_fee()
        nonce      = tx.get_nonce()

        sender_acct = self.accounts.get_account(sender_pk)
        if (sender_acct is None
            or sender_acct.nonce() != nonce
            or sender_acct.balance() < amount + fee):
            raise ValueError("invalid or unaffordable transaction")

        # --- debit sender --------------------------------------------------
        self.accounts.set_account(
            sender_pk,
            Account.create(
                balance=sender_acct.balance() - amount - fee,
                data=sender_acct.data(),
                nonce=sender_acct.nonce() + 1,
            )
        )

        # --- destination handling -----------------------------------------
        if recip_pk == TREASURY:
            treasury = self.accounts.get_account(TREASURY)

            trie = PatriciaTrie(node_get=None, root_hash=treasury.data())
            stake_bytes = trie.get(sender_pk) or b""
            current_stake = int.from_bytes(stake_bytes, "big") if stake_bytes else 0

            if amount > 0:
                # stake **deposit**
                trie.put(sender_pk, (current_stake + amount).to_bytes(32, "big"))
                new_treas_bal = treasury.balance() + amount
            else:
                # stake **withdrawal**
                if current_stake == 0:
                    raise ValueError("no stake to withdraw")
                # move stake back to sender balance
                sender_after = self.accounts.get_account(sender_pk)
                self.accounts.set_account(
                    sender_pk,
                    Account.create(
                        balance=sender_after.balance() + current_stake,
                        data=sender_after.data(),
                        nonce=sender_after.nonce(),
                    )
                )
                trie.delete(sender_pk)
                new_treas_bal = treasury.balance()  # treasury balance unchanged

            # write back treasury with new trie root
            self.accounts.set_account(
                TREASURY,
                Account.create(
                    balance=new_treas_bal,
                    data=trie.root_hash,
                    nonce=treasury.nonce(),
                )
            )

        else:
            recip_acct = self.accounts.get_account(recip_pk) or Account.create(0, b"", 0)
            self.accounts.set_account(
                recip_pk,
                Account.create(
                    balance=recip_acct.balance() + amount,
                    data=recip_acct.data(),
                    nonce=recip_acct.nonce(),
                )
            )

        # --- accumulate fee & record --------------------------------------
        self.total_fees += fee
        self.tx_hashes.append(tx.hash)
        self.transactions_count += 1
