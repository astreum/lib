from __future__ import annotations

from typing import Dict, List, Optional, Union, Any, Callable

from .merkle import MerkleTree
from ..crypto import ed25519

_FIELD_ORDER: List[str] = [
    "amount",
    "balance",
    "fee",
    "nonce",
    "recipient_pk",
    "sender_pk",
]

_INT_FIELDS = {"amount", "balance", "fee", "nonce"}

def _int_to_min_bytes(i: int) -> bytes:
    length = (i.bit_length() + 7) // 8 or 1
    return i.to_bytes(length, "big")

class Transaction:
    # init
    def __init__(
        self,
        tx_hash: bytes,
        *,
        tree: Optional[MerkleTree] = None,
        get_node_fn: Optional[Callable[[bytes], Optional[bytes]]] = None,
    ) -> None:
        self._hash = tx_hash
        self._tree = tree
        self._field_cache: Dict[str, Union[int, bytes]] = {}

        if self._tree and get_node_fn:
            self._tree.set_external_node_fetcher(get_node_fn)

    @classmethod
    def create(
        cls,
        *,
        amount: int,
        balance: int,
        fee: int,
        nonce: int,
        recipient_pk: bytes,
        sender_pk: bytes,
    ) -> "Transaction":
        vals: Dict[str, Any] = locals().copy()
        leaves = [
            vals[name] if isinstance(vals[name], bytes) else _int_to_min_bytes(vals[name])
            for name in _FIELD_ORDER
        ]

        tree = MerkleTree.from_leaves(leaves)
        return cls(tx_hash=tree.root_hash, tree=tree)

    @property
    def hash(self) -> bytes:
        return self._hash

    def _require_tree(self) -> MerkleTree:
        if not self._tree:
            raise ValueError("Merkle tree unavailable for this Transaction")
        return self._tree

    def _field(self, idx: int, name: str) -> Union[int, bytes]:
        if name in self._field_cache:
            return self._field_cache[name]

        raw = self._require_tree().get(idx)
        if raw is None:
            raise ValueError(f"Leaf {idx} (‘{name}’) missing from Merkle tree")

        value = int.from_bytes(raw, "big") if name in _INT_FIELDS else raw
        self._field_cache[name] = value
        return value

    def get_amount(self) -> int:
        return self._field(0, "amount")
    
    def get_balance(self) -> int:
        return self._field(1, "balance")
    
    def get_fee(self) -> int:
        return self._field(2, "fee")
    
    def get_nonce(self) -> int:
        return self._field(3, "nonce")
    
    def get_recipient_pk(self) -> bytes:
        return self._field(4, "recipient_pk")
    
    def get_sender_pk(self) -> bytes:
        return self._field(5, "sender_pk")
    
    def sign(self, priv: ed25519.Ed25519PrivateKey) -> bytes:
        return priv.sign(self.hash)

    def verify_signature(self, sig: bytes, sender_pk: bytes) -> bool:
        try:
            ed25519.Ed25519PublicKey.from_public_bytes(sender_pk).verify(sig, self.hash)
            return True
        except Exception:
            return False
