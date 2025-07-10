import blake3
from typing import Callable, Dict, List, Optional, Tuple
from astreum import format

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
    
    def put(self, key: bytes, value: bytes) -> None:
        """Insert or update ``key`` with ``value`` in‑place."""
        total_bits = len(key) * 8

        # S1 – Empty trie → create root leaf
        if self.root_hash is None:
            leaf = self._make_node(key, total_bits, value, None, None)
            self.root_hash = leaf.hash()
            return

        # S2 – traversal bookkeeping
        stack: List[Tuple[PatriciaNode, bytes, int]] = []  # (parent, parent_hash, dir_bit)
        node = self._fetch(self.root_hash)
        assert node is not None  # root must exist now
        key_pos = 0

        # S4 – main descent loop
        while True:
            # 4.1 – prefix mismatch? → split
            if not self._match_prefix(node.key, node.key_len, key, key_pos):
                self._split_and_insert(node, stack, key, key_pos, value)
                return

            # 4.2 – consume this prefix
            key_pos += node.key_len

            # 4.3 – matched entire key → update value
            if key_pos == total_bits:
                self._invalidate_hash(node)
                node.value = value
                new_hash = node.hash()
                self._bubble(stack, new_hash)
                return

            # 4.4 – routing bit
            next_bit = self._bit(key, key_pos)
            child_hash = node.child_1 if next_bit else node.child_0

            # 4.6 – no child → easy append leaf
            if child_hash is None:
                self._append_leaf(node, next_bit, key, key_pos, value, stack)
                return

            # 4.7 – push current node onto stack
            stack.append((node, node.hash(), int(next_bit)))

            # 4.8 – fetch child and continue
            node = self._fetch(child_hash)
            if node is None:
                # Dangling pointer – treat as append missing leaf
                self._append_leaf(stack[-1][0], next_bit, key, key_pos, value, stack[:-1])
                return
            key_pos += 1  # consumed routing bit

    def _append_leaf(
        self,
        parent: PatriciaNode,
        dir_bit: bool,
        key: bytes,
        key_pos: int,
        value: bytes,
        stack: List[Tuple[PatriciaNode, bytes, int]],
    ) -> None:
        # key_pos points to routing bit; leaf stores the *rest* after that bit
        tail_len = len(key) * 8 - (key_pos + 1)
        tail_bits, tail_len = self._bit_slice(key, key_pos + 1, tail_len)
        leaf = self._make_node(tail_bits, tail_len, value, None, None)

        # attach
        if dir_bit:
            parent.child_1 = leaf.hash()
        else:
            parent.child_0 = leaf.hash()
        self._invalidate_hash(parent)
        new_parent_hash = parent.hash()
        self._bubble(stack, new_parent_hash)

    def _split_and_insert(
        self,
        node: PatriciaNode,
        stack: List[Tuple[PatriciaNode, bytes, int]],
        key: bytes,
        key_pos: int,
        value: bytes,
    ) -> None:
        """Split ``node`` at first divergent bit and insert new leaf for *key*."""
        # Compute LCP between node.key and remaining key bits
        max_lcp = min(node.key_len, len(key) * 8 - key_pos)
        lcp = 0
        while lcp < max_lcp and self._bit(node.key, lcp) == self._bit(key, key_pos + lcp):
            lcp += 1

        # Common prefix bits → new internal node
        common_bits, common_len = self._bit_slice(node.key, 0, lcp)
        internal = self._make_node(common_bits, common_len, None, None, None)

        # Trim old node prefix
        old_suffix_bits, old_suffix_len = self._bit_slice(node.key, lcp, node.key_len - lcp)
        node.key = old_suffix_bits
        node.key_len = old_suffix_len
        self._invalidate_hash(node)  # will be re‑hashed when attached
        old_div_bit = self._bit(node.key, 0) if old_suffix_len > 0 else False

        # New key leaf
        new_key_tail_len = len(key) * 8 - (key_pos + lcp + 1)
        new_tail_bits, new_tail_len = self._bit_slice(key, key_pos + lcp + 1, new_key_tail_len)
        leaf = self._make_node(new_tail_bits, new_tail_len, value, None, None)
        new_div_bit = self._bit(key, key_pos + lcp)

        # Attach children to internal
        if old_div_bit:
            internal.child_1 = node.hash()
            internal.child_0 = leaf.hash() if not new_div_bit else internal.child_0
        else:
            internal.child_0 = node.hash()
            internal.child_1 = leaf.hash() if new_div_bit else internal.child_1
        self._invalidate_hash(internal)
        internal_hash = internal.hash()

        # Rewire parent link or set as root
        if not stack:
            self.root_hash = internal_hash
            return

        parent, parent_old_hash, dir_bit = stack.pop()
        if dir_bit == 0:
            parent.child_0 = internal_hash
        else:
            parent.child_1 = internal_hash
        self._invalidate_hash(parent)
        parent_new_hash = parent.hash()
        self._bubble(stack, parent_new_hash)


