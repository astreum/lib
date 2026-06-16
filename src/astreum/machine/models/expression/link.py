from __future__ import annotations

from blake3 import blake3

ZERO32 = b"\x00" * 32


class Link:
    __slots__ = ("head", "tail", "head_hash", "tail_hash", "_hash", "_size")

    def __init__(self, head: Expr = None, tail: Expr = None,
                 head_hash: bytes = None, tail_hash: bytes = None):
        self.head = head
        self.tail = tail
        self.head_hash = head_hash
        self.tail_hash = tail_hash

    def __repr__(self):
        if self.head_hash is not None:
            return f"({self.head_hash.hex()[:8]}# . {self.tail_hash.hex()[:8]}#)"
        return f"({self.head} . {self.tail})"

    def hash(self):
        cached = getattr(self, "_hash", None)
        if cached is not None:
            return cached
        if self.head is None and self.tail is None and self.head_hash is None and self.tail_hash is None:
            self._hash = ZERO32
            return ZERO32
        hh = self.head_hash
        if hh is None:
            hh = self.head.hash() if self.head is not None else ZERO32
        th = self.tail_hash
        if th is None:
            th = self.tail.hash() if self.tail is not None else ZERO32
        content_hash = blake3(hh + th).digest()
        self._hash = blake3(b"\x00" + content_hash).digest()
        return self._hash

    def size(self) -> int:
        cached = getattr(self, "_size", None)
        if cached is not None:
            return cached
        if (self.head is None and self.tail is None
                and self.head_hash is None and self.tail_hash is None):
            self._size = 64
            return 64
        h = self.head.size() if self.head is not None else 32
        t = self.tail.size() if self.tail is not None else 32
        self._size = h + t
        return self._size

    def to_bytes(self) -> bytes:
        hh = self.head_hash or (self.head.hash() if self.head is not None else ZERO32)
        th = self.tail_hash or (self.tail.hash() if self.tail is not None else ZERO32)
        return b"\x00" + hh + th
