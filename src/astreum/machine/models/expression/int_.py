from __future__ import annotations

from blake3 import blake3


class Int:
    __slots__ = ("value", "_hash")

    def __init__(self, value: int):
        self.value = value

    def __repr__(self):
        return str(self.value)

    def _encoded(self) -> bytes:
        n = max(1, (self.value.bit_length() + 8) // 8)
        return self.value.to_bytes(n, "little", signed=True)

    def hash(self):
        cached = getattr(self, "_hash", None)
        if cached is not None:
            return cached
        content_hash = blake3(self._encoded()).digest()
        self._hash = blake3(b"\x03" + content_hash).digest()
        return self._hash

    def size(self) -> int:
        return len(self._encoded())

    def to_bytes(self) -> bytes:
        return b"\x03" + self._encoded()
