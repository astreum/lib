from __future__ import annotations

from blake3 import blake3


class Bytes:
    __slots__ = ("value", "_hash")

    def __init__(self, value: bytes):
        self.value = value

    def __repr__(self):
        if not self.value:
            return "0"
        int_value = int.from_bytes(self.value, "little", signed=True)
        return f"{int_value}"

    def hash(self):
        cached = getattr(self, "_hash", None)
        if cached is not None:
            return cached
        content_hash = blake3(self.value).digest()
        self._hash = blake3(b"\x02" + content_hash).digest()
        return self._hash

    def size(self) -> int:
        return len(self.value)

    def to_bytes(self) -> bytes:
        return b"\x02" + self.value
