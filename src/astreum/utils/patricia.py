import blake3
from typing import Callable, Dict, List, Optional
from astreum import format

EMPTY_HASH = b"\x00" * 32

class PatriciaNode:
    def __init__(
        self,
        key_len: int,
        key: bytes,
        value: Optional[bytes],
        child_0: Optional[bytes],
        child_1: Optional[bytes]
    ):
        self.key_len = key_len
        self.key = key
        self.value = value
        self.child_0 = child_0
        self.child_1 = child_1
        self._hash: bytes | None = None

    def to_bytes(self) -> bytes:
        return format.encode([self.key_len, self.key, self.value, self.child_0, self.child_1])

    @classmethod
    def from_bytes(cls, blob: bytes) -> "PatriciaNode":
        key_len, key, value, child_0, child_1 = format.decode(blob)
        return cls(key_len, key, value, child_0, child_1)
    
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
        self.nodes: Dict[bytes, PatriciaNode] = {}
        self.root_hash: Optional[bytes] = root_hash

    @staticmethod
    def _bit(buf: bytes, idx: int) -> bool:
        byte_i, offset = divmod(idx, 8)
        return ((buf[byte_i] >> (7 - offset)) & 1) == 1

    @classmethod
    def _match_prefix(
        cls,
        prefix: bytes,
        prefix_len: int,
        key: bytes,
        key_bit_offset: int,
    ) -> bool:
        if key_bit_offset + prefix_len > len(key) * 8:
            return False

        for i in range(prefix_len):
            if cls._bit(prefix, i) != cls._bit(key, key_bit_offset + i):
                return False
        return True

    def _fetch(self, h: bytes) -> Optional[PatriciaNode]:
        node = self.nodes.get(h)
        if node is None:
            raw = self._node_get(h)
            if raw is None:
                return None
            node = PatriciaNode.from_bytes(raw)
            self.nodes[h] = node
        return node

    def get(self, key: bytes) -> Optional["PatriciaNode"]:
        """Return the node that stores *key*, or ``None`` if absent."""
        if self.root_hash is None:
            return None

        node = self._fetch(self.root_hash)
        if node is None:
            return None

        key_pos = 0

        while node is not None:
            # 1️⃣ Verify that this node's (possibly sub‑byte) prefix matches.
            if not self._match_prefix(node.key, node.key_len, key, key_pos):
                return None
            key_pos += node.key_len

            # 2️⃣ If every bit of *key* has been matched, success only if the
            #     node actually stores a value.
            if key_pos == len(key) * 8:
                return node if node.value is not None else None

            # 3️⃣ Decide which branch to follow using the next bit of *key*.
            try:
                next_bit = self._bit(key, key_pos)
            except IndexError:  # key ended prematurely
                return None

            child_hash = node.child_1 if next_bit else node.child_0
            if child_hash is None:  # dead end – key not present
                return None

            # 4️⃣ Fetch the child node via unified helper.
            node = self._fetch(child_hash)
            if node is None:  # dangling pointer
                return None

            key_pos += 1  # we just consumed one routing bit

        return None


