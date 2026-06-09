from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...machine.models.expression import Expr, ZERO32
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

        account_expr: Optional[Expr] = self._trie.get(node, address)
        if account_expr is None:
            return None

        from ...machine.models.expression import resolve_list_exprs
        from ...consensus.account.create import create_account
        from ...utils.integer import bytes_to_int

        nodes, missed = resolve_list_exprs(node, account_expr)
        if missed or len(nodes) != 5:
            return None

        data_node, counter_node, code_node, channels_node, balance_node = nodes

        detail_values: list[bytes] = []
        for n in (data_node, counter_node, code_node, channels_node, balance_node):
            if isinstance(n, Expr.Bytes):
                detail_values.append(n.value)
            elif isinstance(n, Expr.Link):
                detail_values.append(n.head_hash if n.head_hash is not None else n.hash())
            else:
                return None

        data_bytes, counter_bytes, code_bytes, channels_bytes, balance_bytes = detail_values

        account = create_account(
            balance=bytes_to_int(balance_bytes),
            data_hash=data_bytes,
            channels_hash=channels_bytes,
            counter=bytes_to_int(counter_bytes),
            code_hash=code_bytes,
        )
        account._expr = account_expr
        self._cache[address] = account
        return account

    def set_account(self, address: bytes, account: Account) -> None:
        self._cache[address] = account

    def update_trie(self, node: Any) -> Optional[bytes]:
        """Serialise cached accounts into the trie. Returns the new root hash."""
        for address, account in self._cache.items():
            account.data_hash = account.data.root_hash or ZERO32
            account.channels_hash = account.channels.root_hash or ZERO32
            self._trie.put(node, address, account.expr())
        return self._trie.root_hash


def _trie_nodes_exprs(trie: Trie) -> List[Expr]:
    """Return exprs for all nodes in a trie and their inline values."""
    exprs: List[Expr] = []
    for node in trie.nodes.values():
        exprs.append(node.expr())
        val = node.value
        if val is not None and not isinstance(val, bytes):
            exprs.append(val)
    return exprs


def extract_accounts_exprs(accounts: Accounts) -> List[Expr]:
    """Collect every expr that must be in storage to reconstruct `accounts`."""
    exprs: List[Expr] = []

    exprs.extend(_trie_nodes_exprs(accounts._trie))

    for acct in accounts._cache.values():
        acct_expr = acct.expr()
        exprs.append(acct_expr)

        exprs.extend(_trie_nodes_exprs(acct.data))
        exprs.extend(_trie_nodes_exprs(acct.channels))

    return exprs
