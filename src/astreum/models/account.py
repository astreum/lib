from __future__ import annotations

from typing import Optional, Callable

from .merkle import MerkleTree

_FIELD_ORDER = ["balance", "data", "nonce"]
_INT_FIELDS = {"balance", "nonce"}

def _int_to_min_bytes(i: int) -> bytes:
    length = (i.bit_length() + 7) // 8 or 1
    return i.to_bytes(length, "big")

class Account:
    def __init__(
        self,
        body_hash: bytes,
        *,
        body_tree: Optional[MerkleTree] = None,
        get_node_fn: Optional[Callable[[bytes], Optional[bytes]]] = None,
    ) -> None:
        self._body_hash = body_hash
        self._body_tree = body_tree
        self._balance: Optional[int] = None
        self._data: Optional[bytes] = None
        self._nonce: Optional[int] = None

        if self._body_tree and get_node_fn:
            self._body_tree._node_get = get_node_fn

    @classmethod
    def create(
        cls,
        balance: int,
        data: bytes,
        nonce: int,
    ) -> Account:
        """Build an Account body from explicit fields in alphabetical order."""
        # prepare values dict
        values = {"balance": balance, "data": data, "nonce": nonce}

        # build leaves in alphabetical order
        leaves: list[bytes] = []
        for name in _FIELD_ORDER:
            v = values[name]
            if name in _INT_FIELDS:
                leaves.append(_int_to_min_bytes(v))  # type: ignore[arg-type]
            else:
                leaves.append(v)

        tree = MerkleTree.from_leaves(leaves)
        return cls(tree.root_hash, body_tree=tree)

    def body_hash(self) -> bytes:
        """Return the Merkle root of the account body."""
        return self._body_hash

    def _require_tree(self) -> MerkleTree:
        if not self._body_tree:
            raise ValueError("Body tree unavailable for this Account")
        return self._body_tree

    def balance(self) -> int:
        """Fetch & cache the `balance` field (leaf 0)."""
        if self._balance is not None:
            return self._balance
        raw = self._require_tree().get(0)
        if raw is None:
            raise ValueError("Merkle leaf 0 (balance) missing")
        self._balance = int.from_bytes(raw, "big")
        return self._balance

    def data(self) -> bytes:
        """Fetch & cache the `data` field (leaf 1)."""
        if self._data is not None:
            return self._data
        raw = self._require_tree().get(1)
        if raw is None:
            raise ValueError("Merkle leaf 1 (data) missing")
        self._data = raw
        return self._data

    def nonce(self) -> int:
        """Fetch & cache the `nonce` field (leaf 2)."""
        if self._nonce is not None:
            return self._nonce
        raw = self._require_tree().get(2)
        if raw is None:
            raise ValueError("Merkle leaf 2 (nonce) missing")
        self._nonce = int.from_bytes(raw, "big")
        return self._nonce
