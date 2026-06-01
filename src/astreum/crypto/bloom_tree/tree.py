from __future__ import annotations

from collections.abc import Callable

from .node import BloomNode
from ..bloom_filter import bloom_insert, bloom_test


class BloomTree:
    """Binary bloom tree for a 1024-block chunk."""

    def __init__(self, chunk_idx: int):
        self.chunk_idx = chunk_idx
        self.root: BloomNode | None = None

    def insert(self, offset: int, block_hash: bytes, variants: list[bytes]) -> None:
        """Insert search variants for a block at `offset` within the chunk."""
        if self.root is None:
            self.root = BloomNode(level=0)

        self._walk(self.root, offset, 0, 1024, block_hash, variants, level=0)

    def _walk(self, node: BloomNode, offset: int, lo: int, hi: int,
              block_hash: bytes, variants: list[bytes], level: int) -> None:
        for v in variants:
            bloom_insert(node.filter, v)

        if node.is_leaf:
            return

        mid = (lo + hi) // 2
        child_level = level + 1
        child_is_leaf = child_level == 10
        if offset < mid:
            if node.left is None:
                node.left = BloomNode(level=child_level,
                                      start_hash=block_hash if child_is_leaf else None)
            self._walk(node.left, offset, lo, mid, block_hash, variants, child_level)
        else:
            if node.right is None:
                node.right = BloomNode(level=child_level,
                                       start_hash=block_hash if child_is_leaf else None)
            self._walk(node.right, offset, mid, hi, block_hash, variants, child_level)


def bloom_search(node: BloomNode | None, element: bytes) -> list[bytes]:
    """Search the bloom tree for `element`. Returns list of leaf block hashes
    where the element may be present. Empty list = definitely absent."""
    if node is None:
        return []
    if not bloom_test(node.filter, element):
        return []
    if node.is_leaf:
        return [node.start_hash] if node.start_hash else []

    results: list[bytes] = []
    if node.left is not None:
        results.extend(bloom_search(node.left, element))
    if node.right is not None:
        results.extend(bloom_search(node.right, element))
    return results
