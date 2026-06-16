from __future__ import annotations

from blake3 import blake3


class String:
    __slots__ = ("value", "_hash")

    def __init__(self, value: str):
        self.value = value

    def __repr__(self):
        return f'"{self.value}"'

    def _encoded(self) -> bytes:
        return self.value.encode("utf-8")

    def hash(self):
        cached = getattr(self, "_hash", None)
        if cached is not None:
            return cached
        content_hash = blake3(self._encoded()).digest()
        self._hash = blake3(b"\x05" + content_hash).digest()
        return self._hash

    def size(self) -> int:
        return len(self._encoded())

    def to_bytes(self) -> bytes:
        return b"\x05" + self._encoded()
