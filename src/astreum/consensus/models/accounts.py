from __future__ import annotations

from typing import Any, Dict, List, Optional

from astreum.expression import Expr, ZERO32
from astreum.storage.radix import RadixTree, get_radix_node_expr, get_from_radix_tree, put_in_radix_tree
from astreum.consensus.account import Account


class Accounts:
    def __init__(
        self,
        root_hash: Optional[bytes] = None,
    ) -> None:
        self._trie = RadixTree(root_hash=root_hash)
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

        account_expr: Optional[Expr] = get_from_radix_tree(self._trie, node, address)
        if account_expr is None:
            return None

        from astreum.expression import resolve_list_exprs
        from astreum.consensus.account.create import create_account

        nodes, missed = resolve_list_exprs(node, account_expr)
        if missed or len(nodes) != 5:
            return None

        data_node, counter_node, code_node, channels_node, balance_node = nodes

        if not data_node._tag == "link":
            return None
        if not counter_node._tag == "int":
            return None
        if not code_node._tag == "link":
            return None
        if not channels_node._tag == "link":
            return None
        if not balance_node._tag == "int":
            return None

        account = create_account(
            balance=balance_node.value,
            data_hash=data_node._head_hash if data_node._head_hash is not None else data_node.hash(),
            channels_hash=channels_node._head_hash if channels_node._head_hash is not None else channels_node.hash(),
            counter=counter_node.value,
            code_hash=code_node._head_hash if code_node._head_hash is not None else code_node.hash(),
        )
        self._cache[address] = account
        return account

    def set_account(self, address: bytes, account: Account) -> None:
        self._cache[address] = account

    def update_trie(self, node: Any) -> Optional[bytes]:
        for address, account in self._cache.items():
            account.data_hash = account.data.root_hash or ZERO32
            account.channels_hash = account.channels.root_hash or ZERO32
            put_in_radix_tree(self._trie, node, address, account.expr())
        return self._trie.root_hash


def _trie_nodes_exprs(trie: RadixTree) -> List[Expr]:
    exprs: List[Expr] = []
    for node in trie.nodes.values():
        exprs.append(get_radix_node_expr(node))
        val = node.value
        if val is not None and not isinstance(val, bytes):
            exprs.append(val)
    return exprs


def extract_accounts_exprs(accounts: Accounts) -> List[Expr]:
    exprs: List[Expr] = []

    exprs.extend(_trie_nodes_exprs(accounts._trie))

    for acct in accounts._cache.values():
        acct_expr = acct.expr()
        exprs.append(acct_expr)

        exprs.extend(_trie_nodes_exprs(acct.data))
        exprs.extend(_trie_nodes_exprs(acct.channels))

    return exprs
