import blake3
from typing import Callable, Dict, List, Optional
from astreum import format

EMPTY_HASH = b"\x00" * 32

class PatriciaNode:
    def __init__(
        self,
        key_len: int,
        key_bits: bytes,
        value: bytes,
        children: List[bytes]|None = None
    ):
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

class PatriciaTrie:
    def __init__(
        self,
        node_get: Callable[[bytes], Optional[bytes]],
        root_hash: Optional[bytes] = None,
    ) -> None:
        self._node_get = node_get
        self.nodes: Dict[bytes, bytes] = {}
        self.root_hash: Optional[bytes] = root_hash
