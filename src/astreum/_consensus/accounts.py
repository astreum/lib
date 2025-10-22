from __future__ import annotations

from typing import Any, Dict, Optional

from .._storage.patricia import PatriciaTrie
from .account import Account


class Accounts:
    def __init__(
        self,
        root_hash: Optional[bytes] = None,
    ) -> None:
        self._trie = PatriciaTrie(root_hash=root_hash)
        self._cache: Dict[bytes, Account] = {}

    @property
    def root_hash(self) -> Optional[bytes]:
        return self._trie.root_hash

    def get_account(self, address: bytes, node: Optional[Any] = None) -> Optional[Account]:
        cached = self._cache.get(address)
        if cached is not None:
            return cached

        if node is None:
            raise ValueError("Accounts requires a node reference for trie access")

        account_id: Optional[bytes] = self._trie.get(node, address)
        if account_id is None:
            return None

        account = Account.from_atom(node, account_id)
        self._cache[address] = account
        return account

    def set_account(self, address: bytes, account: Account) -> None:
        self._cache[address] = account
