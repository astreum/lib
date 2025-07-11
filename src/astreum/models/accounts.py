from __future__ import annotations
from typing import Dict, Optional, Callable
from .patricia import PatriciaTrie
from .account import Account

class Accounts:
    def __init__(
        self,
        root_hash: Optional[bytes] = None,
        global_get_fn: Optional[Callable[[bytes], Optional[bytes]]] = None,
    ) -> None:
        self._global_get_fn = global_get_fn
        self._trie = PatriciaTrie(node_get=global_get_fn, root_hash=root_hash)
        self._cache: Dict[bytes, Account] = {}

    @property
    def root_hash(self) -> Optional[bytes]:
        return self._trie.root_hash

    def get_account(self, address: bytes) -> Optional[Account]:
        if address in self._cache:
            return self._cache[address]

        body_hash: Optional[bytes] = self._trie.get(address)
        if body_hash is None:
            return None

        acc = Account(body_hash, get_node_fn=self._global_get_fn)
        self._cache[address] = acc
        return acc

    def set_account(self, address: bytes, account: Account) -> None:
        self._cache[address] = account
        self._trie.put(address, account.body_hash())
