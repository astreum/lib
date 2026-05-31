from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...machine.models.expression import Expr, resolve_inner_exprs
from ...machine.models.expression import ZERO32
from ...storage.models.trie import Trie
from ...consensus.account import Account, get_account_from_storage


class Accounts:
    def __init__(
        self,
        root_hash: Optional[bytes] = None,
    ) -> None:
        self._trie = Trie(root_hash=root_hash)
        self._cache: Dict[bytes, Account] = {}
        self.pending_exprs: List[Expr] = []

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

        account = get_account_from_storage(node=node, atom_id=account_id)
        self._cache[address] = account
        return account

    def set_account(self, address: bytes, account: Account) -> None:
        self._cache[address] = account

    def update_trie(self, node: Any) -> list:
        """
        Serialise cached accounts, ensure their associated tries are materialised,
        and return all exprs that must be stored.
        """

        def _node_atoms(trie: Trie) -> list:
            emitted: list = []
            if not trie.nodes:
                return emitted
            for node_hash in sorted(trie.nodes.keys()):
                trie_node = trie.nodes[node_hash]
                expr = trie_node.expr()
                if expr.hash() != node_hash:
                    continue
                emitted.append(expr)
            return emitted

        account_trie_exprs: list = []
        account_exprs: list = []
        pending_exprs = list(self.pending_exprs)

        for address, account in self._cache.items():
            account.data_hash = account.data.root_hash or ZERO32
            account.channels_hash = account.channels.root_hash or ZERO32
            account_trie_exprs.extend(_node_atoms(account.data))
            account_trie_exprs.extend(_node_atoms(account.channels))

            account_id = account.expr().hash()
            self._trie.put(node, address, account_id)
            inner_exprs, _ = resolve_inner_exprs(node, account.expr())
            account_exprs.extend(inner_exprs)

        trie_exprs = _node_atoms(self._trie)
        return pending_exprs + account_trie_exprs + account_exprs + trie_exprs
