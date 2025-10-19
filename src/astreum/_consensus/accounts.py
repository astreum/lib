from __future__ import annotations
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Tuple

from .._storage.atom import Atom
from .._storage.patricia import PatriciaTrie
from .account import Account


class Accounts:
    def __init__(
        self,
        root_hash: Optional[bytes] = None,
    ) -> None:
        self._trie = PatriciaTrie(root_hash=root_hash)
        self._cache: Dict[bytes, Account] = {}
        self._staged: Dict[bytes, Account] = {}
        self._staged_hashes: Dict[bytes, bytes] = {}
        self._staged_atoms: Dict[bytes, Iterable[Atom]] = {}
        self._node: Optional[Any] = None

    @property
    def root_hash(self) -> Optional[bytes]:
        return self._trie.root_hash

    def _resolve_node(self, node: Optional[Any]) -> Any:
        if node is not None:
            if self._node is None:
                self._node = node
            return node
        if self._node is None:
            raise ValueError("Accounts requires a node reference for trie access")
        return self._node

    def get_account(self, address: bytes, *, node: Optional[Any] = None) -> Optional[Account]:
        if address in self._staged:
            return self._staged[address]

        cached = self._cache.get(address)
        if cached is not None:
            return cached

        storage_node = self._resolve_node(node)
        account_id: Optional[bytes] = self._trie.get(storage_node, address)
        if account_id is None:
            return None

        account = Account.from_atom(storage_node, account_id)
        self._cache[address] = account
        return account

    def set_account(self, address: bytes, account: Account) -> None:
        account_hash, atoms = account.to_atom()
        self._staged[address] = account
        self._staged_hashes[address] = account_hash
        self._staged_atoms[address] = tuple(atoms)
        self._cache[address] = account

    def staged_items(self) -> Iterable[Tuple[bytes, Account]]:
        return self._staged.items()

    def staged_hashes(self) -> Dict[bytes, bytes]:
        return dict(self._staged_hashes)

    def staged_atoms(self) -> Dict[bytes, Iterable[Atom]]:
        return {addr: tuple(atoms) for addr, atoms in self._staged_atoms.items()}
