from __future__ import annotations

from astreum.crypto.bloom_filter import BloomFilter


class BloomNode:
    """A node in the binary bloom tree. Wraps a BloomFilter and holds
    in-memory child references. Children are not serialized — they are
    fetched from storage by deterministic key.

    Level is encoded in the key (bloom:chunk:{idx}:{level}:{index}).
    Width = 1024 >> level.  Leaf = level 10 (width 1).
    start_hash is only set for leaves (the block hash returned by search)."""

    def __init__(self, level: int, start_hash: bytes | None = None):
        self.level = level
        self.start_hash = start_hash
        self.filter = BloomFilter()
        if start_hash is not None:
            self.filter.start_hash = start_hash
        self.left: BloomNode | None = None
        self.right: BloomNode | None = None
        self._left_hash: bytes | None = None
        self._right_hash: bytes | None = None
        self._expr = None  # cached expr

    @property
    def width(self) -> int:
        return 1024 >> self.level

    @property
    def is_leaf(self) -> bool:
        return self.level == 10

    def expr(self):
        if self._expr is not None:
            return self._expr
        self._expr = self.to_expr()
        return self._expr

    def to_expr(self):
        from astreum.crypto.bloom_tree.expr import bloom_node_to_expr
        return bloom_node_to_expr(self)

    @classmethod
    def from_expr(cls, expr, *, node_get=None):
        from astreum.crypto.bloom_tree.expr import bloom_node_from_expr
        return bloom_node_from_expr(expr)
