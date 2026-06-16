from __future__ import annotations

from blake3 import blake3


class Symbol:
    __slots__ = ("value", "_hash")

    def __init__(self, value: str):
        self.value = value

    def __repr__(self):
        return f"{self.value}"

    def hash(self):
        cached = getattr(self, "_hash", None)
        if cached is not None:
            return cached
        content_hash = blake3(self.value.encode("utf-8")).digest()
        self._hash = blake3(b"\x01" + content_hash).digest()
        return self._hash

    def size(self) -> int:
        return len(self.value.encode("utf-8"))

    def to_bytes(self) -> bytes:
        val = self.value.encode("utf-8")
        return b"\x01" + val
