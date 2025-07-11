"""Account‐state management built on a PatriciaTrie.

Only the *initial skeleton* is provided here per current request:
  • __init__: wrap an existing trie root (or start empty).
  • get_account: look up an Account object, using a cache so multiple
    balance/nonce updates in one block operate on the same instance.

Additional mutation helpers (set_account, change_balance, etc.) will be
added next, once confirmed.
"""
from __future__ import annotations

from typing import Dict, Optional, Callable

from .patricia import PatriciaTrie
from .account import Account


class Accounts:
    """Light wrapper around a PatriciaTrie (address → body_hash) plus
    an in‑memory cache of Account objects currently being worked on.
    """

    # ------------------------------------------------------------
    # construction
    # ------------------------------------------------------------
    def __init__(
        self,
        root_hash: Optional[bytes] = None,
        *,
        get_node_fn: Optional[Callable[[bytes], Optional[bytes]]] = None,
    ) -> None:
        """Wrap an existing state trie *or* start empty (root_hash=None).

        `get_node_fn` (optional) is a callback that retrieves raw node bytes
        when the underlying PatriciaTrie encounters an unknown hash – useful
        for disk or network-backed light clients.
        """
        self._remote_get = get_node_fn
        # Instantiate the trie; we pass the external fetcher straight in.
        # PatriciaTrie is expected to accept `node_get` and `root_hash`.
        self._trie = PatriciaTrie(node_get=get_node_fn, root_hash=root_hash)

        # Working‑set cache: address → Account instance
        self._cache: Dict[bytes, Account] = {}

    # ------------------------------------------------------------
    # public introspection
    # ------------------------------------------------------------
    @property
    def root_hash(self) -> Optional[bytes]:
        """Current trie root (updates automatically after puts)."""
        return self._trie.root_hash

    # ------------------------------------------------------------
    # account access – read‑only for now
    # ------------------------------------------------------------
    def get_account(self, address: bytes) -> Optional[Account]:
        """Return an *Account* for `address`, or *None* if it doesn't exist.

        • First check the in‑memory cache (so repeat reads/updates reuse the
          same object).
        • Otherwise look up `body_hash` in the PatriciaTrie.
        • If found, create a lightweight `Account` wrapper, cache it, and
          return it.  The Account is initialised with the same external
          node‑fetcher so its own Merkle lookups can go remote if needed.
        """
        # cache hit → hot path
        if address in self._cache:
            return self._cache[address]

        # trie lookup (raw body_hash)
        body_hash: Optional[bytes] = self._trie.get(address)
        if body_hash is None:
            return None

        # wrap in Account and cache
        acc = Account(body_hash, get_node_fn=self._remote_get)
        self._cache[address] = acc
        return acc
