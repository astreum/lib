from __future__ import annotations

from struct import pack

from blake3 import blake3


class Float:
    __slots__ = ("value", "_hash")

    def __init__(self, value: float):
        self.value = value

    def __repr__(self):
        return str(self.value)

    def _encoded(self) -> bytes:
        return pack("<d", self.value)

    def hash(self):
        cached = getattr(self, "_hash", None)
        if cached is not None:
            return cached
        content_hash = blake3(self._encoded()).digest()
        self._hash = blake3(b"\x04" + content_hash).digest()
        return self._hash

    def size(self) -> int:
        return 8

    def to_bytes(self) -> bytes:
        return b"\x04" + self._encoded()
