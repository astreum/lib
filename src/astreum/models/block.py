from __future__ import annotations

from threading import Thread
from typing import List, Dict, Any, Optional, Union

from astreum.crypto.wesolowski import vdf_generate, vdf_verify
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

    @classmethod
    def genesis(cls, validator_addr: bytes) -> "Block":
        # 1. validator-stakes sub-trie
        stake_trie = PatriciaTrie()
        stake_trie.put(validator_addr, (1).to_bytes(32, "big"))
        stake_root = stake_trie.root_hash

        # 2. three Account bodies
        validator_acct = Account.create(balance=0, data=b"", nonce=0)
        treasury_acct  = Account.create(balance=1, data=stake_root, nonce=0)
        burn_acct = Account.create(balance=0, data=b"", nonce=0)

        # 3. global Accounts structure
        accts = Accounts()
        accts.set_account(validator_addr, validator_acct)
        accts.set_account(b"\x11" * 32, treasury_acct)
        accts.set_account(b"\x00" * 32, burn_acct)
        accounts_hash = accts.root_hash

        # 4. constant body fields for genesis
        body_kwargs = dict(
            block_hash              = b"",
            number                  = 0,
            prev_block_hash         = b"\x00" * 32,
            timestamp               = 0,
            block_time              = 0,
            accounts_hash           = accounts_hash,
            accounts                = accts,
            transactions_total_fees = 0,
            transaction_limit       = 1,
            transactions_root_hash  = b"\x00" * 32,
            transactions_count      = 0,
            delay_difficulty        = 1,
            delay_output            = b"",
            delay_proof             = b"",
            validator_pk            = validator_addr,
            signature               = b"",
        )

        # 5. build and return the block
        return cls.create(**body_kwargs)

    @classmethod
    def build(
        cls,
        previous_block: "Block",
        transactions: List[Transaction],
        *,
        validator_sk,
        natural_rate: float = 0.618,
    ) -> "Block":
        BURN     = b"\x00" * 32

        blk = cls(
            block_hash=b"",
            number=previous_block.number + 1,
            prev_block_hash=previous_block.hash,
            timestamp=previous_block.timestamp + 1,
            accounts_hash=previous_block.accounts_hash,
            transaction_limit=previous_block.transaction_limit,
            transactions_count=0,
            validator_pk=validator_sk.public_key().public_bytes(),
        )

        # ------------------ difficulty via natural_rate -----------------------
        prev_bt   = previous_block.block_time or 0
        prev_diff = previous_block.delay_difficulty or 1
        if prev_bt <= 1:
            blk.delay_difficulty = max(1, int(prev_diff / natural_rate))  # increase
        else:
            blk.delay_difficulty = max(1, int(prev_diff * natural_rate))  # decrease

        # ------------------ launch VDF in background --------------------------
        vdf_result: dict[str, bytes] = {}

        def _vdf_worker():
            y, p = vdf_generate(previous_block.delay_output, blk.delay_difficulty, -4)
            vdf_result["y"] = y
            vdf_result["p"] = p

        Thread(target=_vdf_worker, daemon=True).start()

        # ------------------ process transactions -----------------------------
        for tx in transactions:
            try:
                blk.apply_tx(tx)
            except ValueError:
                break

        # ------------------ split fees --------------------------------------
        burn_amt   = blk.total_fees // 2
        reward_amt = blk.total_fees - burn_amt

        def _credit(addr: bytes, amt: int):
            acc = blk.accounts.get_account(addr) or Account.create(0, b"", 0)
            blk.accounts.set_account(addr, Account.create(acc.balance() + amt, acc.data(), acc.nonce()))

        if burn_amt:
            _credit(BURN, burn_amt)
        if reward_amt:
            _credit(blk.validator_pk, reward_amt)

        # ------------------ update tx limit with natural_rate ---------------
        prev_limit    = previous_block.transaction_limit
        prev_tx_count = previous_block.transactions_count
        grow_thr      = prev_limit * natural_rate
        shrink_thr    = prev_tx_count * natural_rate

        if prev_tx_count > grow_thr:
            blk.transaction_limit = prev_tx_count
        elif prev_tx_count < shrink_thr:
            blk.transaction_limit = max(1, int(prev_limit * natural_rate))
        else:
            blk.transaction_limit = prev_limit

        # ------------------ wait for VDF ------------------------------------
        while "y" not in vdf_result:
            pass
        blk.delay_output = vdf_result["y"]
        blk.delay_proof  = vdf_result["p"]

        # ------------------ timing & roots ----------------------------------
        blk.block_time = blk.timestamp - previous_block.timestamp
        blk.accounts_hash = blk.accounts.root_hash
        blk.transactions_root_hash = MerkleTree.from_leaves(blk.tx_hashes).root_hash
        blk.transactions_total_fees = blk.total_fees

        # ------------------ build full body root ----------------------------
        body_fields = {
            "accounts_hash":           blk.accounts_hash,
            "block_time":              blk.block_time,
            "delay_difficulty":        blk.delay_difficulty,
            "delay_output":            blk.delay_output,
            "delay_proof":             blk.delay_proof,
            "number":                  blk.number,
            "prev_block_hash":         blk.prev_block_hash,
            "timestamp":               blk.timestamp,
            "transaction_limit":       blk.transaction_limit,
            "transactions_count":      blk.transactions_count,
            "transactions_root_hash":  blk.transactions_root_hash,
            "transactions_total_fees": blk.transactions_total_fees,
            "validator_pk":            blk.validator_pk,
        }

        leaves: List[bytes] = []
        for k in sorted(body_fields):
            v = body_fields[k]
            if isinstance(v, bytes):
                leaves.append(v)
            else:
                leaves.append(int(v).to_bytes((v.bit_length() + 7) // 8 or 1, "big"))

        body_root = MerkleTree.from_leaves(leaves).root_hash
        blk.body_tree = MerkleTree.from_leaves([body_root])
        blk.signature = validator_sk.sign(body_root)
        blk.hash = MerkleTree.from_leaves([body_root, blk.signature]).root_hash

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

    def validate_block(self, remote_get_fn) -> bool:
        NAT = 0.618
        _i2b = lambda i: i.to_bytes((i.bit_length() + 7) // 8 or 1, "big")

        # ---------- 1.  block-hash & signature -----------------------------
        blk_mt = MerkleTree(node_get=remote_get_fn, root_hash=self.hash)
        body_root = blk_mt.get(0); sig = blk_mt.get(1)
        ed25519.verify_signature(public_key=self.validator_pk, message=body_root, signature=sig)

        # ---------- 2.  rebuild body_root from fields ----------------------
        f_names = (
            "accounts_hash","block_time","delay_difficulty","delay_output","delay_proof",
            "number","prev_block_hash","timestamp","transaction_limit",
            "transactions_count","transactions_root_hash","transactions_total_fees",
            "validator_pk",
        )
        leaves = [
            v if isinstance(v := self.get_field(n), bytes) else _i2b(v)
            for n in sorted(f_names)
        ]
        if MerkleTree.from_leaves(leaves).root_hash != body_root:
            raise ValueError("body root mismatch")

        # ---------- 3.  previous block header & VDF ------------------------
        prev_mt = MerkleTree(node_get=remote_get_fn, root_hash=self.prev_block_hash)
        prev_body_root, prev_sig = prev_mt.get(0), prev_mt.get(1)
        prev_body_mt  = MerkleTree(node_get=remote_get_fn, root_hash=prev_body_root)
        prev_blk      = Block(block_hash=self.prev_block_hash,
                            body_tree=prev_body_mt, signature=prev_sig)
        prev_out   = prev_blk.get_field("delay_output")
        prev_diff  = prev_blk.get_field("delay_difficulty")
        prev_bt    = prev_blk.get_field("block_time")
        prev_limit = prev_blk.get_field("transaction_limit")
        prev_cnt   = prev_blk.get_field("transactions_count")

        if not vdf_verify(prev_out, self.delay_output, self.delay_proof,
                        T=self.delay_difficulty, D=-4):
            raise ValueError("bad VDF proof")

        # ---------- 4.  replay all txs -------------------------------------
        accs = Accounts(root_hash=prev_blk.get_field("accounts_hash"),
                        node_get=remote_get_fn)
        tx_mt = MerkleTree(node_get=remote_get_fn,
                        root_hash=self.transactions_root_hash)
        if tx_mt.leaf_count() != self.transactions_count:
            raise ValueError("transactions_count mismatch")

        dummy = Block(block_hash=b"", accounts=accs,
                    accounts_hash=accs.root_hash,
                    transaction_limit=prev_limit)
        for i in range(self.transactions_count):
            h  = tx_mt.get(i)
            tm = MerkleTree(node_get=remote_get_fn, root_hash=h)
            tx = Transaction(h, tree=tm, node_get=remote_get_fn)
            dummy.apply_tx(tx)

        # fee split identical to build()
        burn = dummy.total_fees // 2
        rew  = dummy.total_fees - burn
        if burn:
            dummy.accounts.set_account(
                b"\x00"*32,
                Account.create(burn, b"", 0)
            )
        if rew:
            v_acct = dummy.accounts.get_account(self.validator_pk) or Account.create(0,b"",0)
            dummy.accounts.set_account(
                self.validator_pk,
                Account.create(v_acct.balance()+rew, v_acct.data(), v_acct.nonce())
            )

        if dummy.accounts.root_hash != self.accounts_hash:
            raise ValueError("accounts_hash mismatch")

        # ---------- 5.  natural-rate rules --------------------------------
        grow_thr   = prev_limit * NAT
        shrink_thr = prev_cnt * NAT
        expect_lim = prev_cnt if prev_cnt > grow_thr \
            else max(1, int(prev_limit * NAT)) if prev_cnt < shrink_thr \
            else prev_limit
        if self.transaction_limit != expect_lim:
            raise ValueError("tx-limit rule")

        expect_diff = max(1, int(prev_diff / NAT)) if prev_bt <= 1 \
                    else max(1, int(prev_diff * NAT))
        if self.delay_difficulty != expect_diff:
            raise ValueError("difficulty rule")

        return True

