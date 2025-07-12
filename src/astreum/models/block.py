from __future__ import annotations

from typing import List, Dict, Any, Optional, Union

from astreum.models.account import Account
from astreum.models.accounts import Accounts
from astreum.models.patricia import PatriciaTrie
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
        body_tree: Optional[MerkleTree] = None,
        signature: Optional[bytes] = None,
    ) -> None:
        self._block_hash = block_hash
        self._body_tree = body_tree
        self._signature = signature
        # store field names in alphabetical order for consistent indexing
        self._field_names = [
            "accounts_hash",
            "delay_difficulty",
            "delay_output",
            "delay_proof",
            "number",
            "prev_block_hash",
            "timestamp",
            "transaction_limit",
            "transactions_root_hash",
            "transactions_total_fees",
            "validator_pk",
        ]

    @property
    def hash(self) -> bytes:
        """Return the block hash (Merkle root of body_root || signature)."""
        return self._block_hash

    @classmethod
    def create(
        cls,
        number: int,
        prev_block_hash: bytes,
        timestamp: int,
        accounts_hash: bytes,
        transactions_total_fees: int,
        transaction_limit: int,
        transactions_root_hash: bytes,
        delay_difficulty: int,
        delay_output: bytes,
        delay_proof: bytes,
        validator_pk: bytes,
        signature: bytes,
    ) -> Block:
        """Build a new block by hashing the provided fields into Merkle trees."""
        # map fields by name
        field_map: Dict[str, Any] = {
            "accounts_hash": accounts_hash,
            "delay_difficulty": delay_difficulty,
            "delay_output": delay_output,
            "delay_proof": delay_proof,
            "number": number,
            "prev_block_hash": prev_block_hash,
            "timestamp": timestamp,
            "transaction_limit": transaction_limit,
            "transactions_root_hash": transactions_root_hash,
            "transactions_total_fees": transactions_total_fees,
            "validator_pk": validator_pk,
        }
        
        leaves: List[bytes] = []
        for name in sorted(field_map):
            v = field_map[name]
            if isinstance(v, bytes):
                leaf_bytes = v
            elif isinstance(v, int):
                length = (v.bit_length() + 7) // 8 or 1
                leaf_bytes = v.to_bytes(length, "big")
            else:
                raise TypeError(f"Unsupported field type for '{name}': {type(v)}")
            leaves.append(leaf_bytes)
        
        body_tree = MerkleTree.from_leaves(leaves)
        body_root = body_tree.root_hash
        top_tree = MerkleTree.from_leaves([body_root, signature])
        block_hash = top_tree.root_hash

        return cls(block_hash, body_tree, signature)

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
