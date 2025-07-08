import blake3
from typing import List
from astreum import format


class PatriciaNode:
    def __init__(self,
                 key_len: int,
                 key_bits: bytes,
                 value: bytes,
                 children: List[bytes]):
        self.key_len   = key_len
        self.key_bits  = key_bits
        self.value     = value
        self.children  = children
        self._hash: bytes | None = None

    def to_bytes(self) -> bytes:
        key_field = bytes([self.key_len]) + self.key_bits
        return format.encode([key_field, self.value, self.children])

    @classmethod
    def from_bytes(cls, blob: bytes) -> "PatriciaNode":
        key_field, value, children = format.decode(blob)
        key_len   = key_field[0]
        key_bits  = key_field[1:]
        return cls(key_len, key_bits, value, children)
    
    def hash(self) -> bytes:
        if self._hash is None:
            self._hash = blake3.blake3(self.to_bytes()).digest()
        return self._hash
