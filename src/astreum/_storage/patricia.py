import blake3
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from .atom import Atom, ZERO32

if TYPE_CHECKING:
    from .._node import Node

class PatriciaNode:
    """
    A node in a compressed-key Patricia trie.

    Attributes:
        key_len (int): Number of bits in the `key` prefix that are meaningful.
        key (bytes): The MSB-aligned bit prefix (zero-padded in last byte).
        value (Optional[bytes]): Stored payload (None for internal nodes).
        child_0 (Optional[bytes]): Hash pointer for next-bit == 0.
        child_1 (Optional[bytes]): Hash pointer for next-bit == 1.
    """

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
        self._hash: Optional[bytes] = None

    def hash(self) -> bytes:
        """
        Compute and cache the BLAKE3 hash of this node's serialized form.
        """
        if self._hash is None:
            self._hash = blake3.blake3(self.to_bytes()).digest()
        return self._hash
    
    def to_atoms(self) -> Tuple[bytes, List[Atom]]:
        """
        Materialise this node as a flat atom chain containing the fields in a
        traversal-friendly order: key length prefix (single byte) + key bytes,
        child_0 hash, child_1 hash, and value bytes. Returns the head atom hash
        and the atom list.
        """
        if self.key_len > 255:
            raise ValueError("Patricia key length > 255 bits cannot be encoded in a single atom field")

        entries: List[bytes] = [
            bytes([self.key_len]) + self.key,
            self.child_0 or ZERO32,
            self.child_1 or ZERO32,
            self.value or b"",
        ]

        atoms: List[Atom] = []
        next_hash = ZERO32
        for payload in reversed(entries):
            atom = Atom.from_data(data=payload, next_hash=next_hash)
            atoms.append(atom)
            next_hash = atom.object_id()

        head = next_hash
        atoms.reverse()
        return head, atoms

    @classmethod
    def from_atoms(
        cls,
        node: "Node",
        head_hash: bytes,
    ) -> "PatriciaNode":
        """
        Reconstruct a node from the atom chain rooted at `head_hash`, using the
        supplied `node` instance to resolve atom object ids.
        """
        if head_hash == ZERO32:
            raise ValueError("empty atom chain for Patricia node")

        entries: List[bytes] = []
        current = head_hash
        hops = 0

        while current != ZERO32 and hops < 4:
            atom = node._local_get(current)
            if atom is None:
                raise ValueError("missing atom while decoding Patricia node")
            entries.append(atom.data)
            current = atom.next
            hops += 1

        if current != ZERO32:
            raise ValueError("too many fields while decoding Patricia node")

        if len(entries) != 4:
            raise ValueError("incomplete atom sequence for Patricia node")

        key_entry = entries[0]
        if not key_entry:
            raise ValueError("missing key entry while decoding Patricia node")
        key_len = key_entry[0]
        key = key_entry[1:]
        child_0 = entries[1] if entries[1] != ZERO32 else None
        child_1 = entries[2] if entries[2] != ZERO32 else None
        value = entries[3]

        return cls(key_len=key_len, key=key, value=value, child_0=child_0, child_1=child_1)

class PatriciaTrie:
    """
    A compressed-key Patricia trie supporting get and put.
    """

    def __init__(
        self,
        root_hash: Optional[bytes] = None,
    ) -> None:
        """
        :param root_hash: optional hash of existing root node
        """
        self.nodes: Dict[bytes, PatriciaNode] = {}
        self.root_hash = root_hash

    @staticmethod
    def _bit(buf: bytes, idx: int) -> bool:
        """
        Return the bit at position `idx` (MSB-first) from `buf`.
        """
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
        """
        Check whether the `prefix_len` bits of `prefix` match
        bits in `key` starting at `key_bit_offset`.
        """
        total_bits = len(key) * 8
        if key_bit_offset + prefix_len > total_bits:
            return False
        for i in range(prefix_len):
            if cls._bit(prefix, i) != cls._bit(key, key_bit_offset + i):
                return False
        return True

    def _fetch(self, storage_node: "Node", h: bytes) -> Optional[PatriciaNode]:
        """
        Fetch a node by hash, consulting the in-memory cache first and falling
        back to the atom storage provided by `storage_node`.
        """
        cached = self.nodes.get(h)
        if cached is not None:
            return cached

        if storage_node._local_get(h) is None:
            return None

        pat_node = PatriciaNode.from_atoms(storage_node, h)
        self.nodes[h] = pat_node
        return pat_node

    def get(self, storage_node: "Node", key: bytes) -> Optional[bytes]:
        """
        Return the stored value for `key`, or None if absent.
        """
        # Empty trie?
        if self.root_hash is None:
            return None

        current = self._fetch(storage_node, self.root_hash)
        if current is None:
            return None

        key_pos = 0  # bit offset into key

        while current is not None:
            # 1) Check that this node's prefix matches the key here
            if not self._match_prefix(current.key, current.key_len, key, key_pos):
                return None
            key_pos += current.key_len

            # 2) If we've consumed all bits of the search key:
            if key_pos == len(key) * 8:
                # Return value only if this node actually stores one
                return current.value

            # 3) Decide which branch to follow via next bit
            try:
                next_bit = self._bit(key, key_pos)
            except IndexError:
                return None

            child_hash = current.child_1 if next_bit else current.child_0
            if child_hash is None:
                return None  # dead end

            # 4) Fetch child and continue descent
            current = self._fetch(storage_node, child_hash)
            if current is None:
                return None  # dangling pointer

            key_pos += 1  # consumed routing bit

        return None

    def put(self, storage_node: "Node", key: bytes, value: bytes) -> None:
        """
        Insert or update `key` with `value` in-place.
        """
        total_bits = len(key) * 8

        # S1 – Empty trie → create root leaf
        if self.root_hash is None:
            leaf = self._make_node(key, total_bits, value, None, None)
            self.root_hash = leaf.hash()
            return

        # S2 – traversal bookkeeping
        stack: List[Tuple[PatriciaNode, bytes, int]] = []  # (parent, parent_hash, dir_bit)
        current = self._fetch(storage_node, self.root_hash)
        assert current is not None
        key_pos = 0

        # S4 – main descent loop
        while True:
            # 4.1 – prefix mismatch? → split
            if not self._match_prefix(current.key, current.key_len, key, key_pos):
                self._split_and_insert(current, stack, key, key_pos, value)
                return

            # 4.2 – consume this prefix
            key_pos += current.key_len

            # 4.3 – matched entire key → update value
            if key_pos == total_bits:
                old_hash = current.hash()
                current.value = value
                self._invalidate_hash(current)
                new_hash = current.hash()
                if new_hash != old_hash:
                    self.nodes.pop(old_hash, None)
                self.nodes[new_hash] = current
                self._bubble(stack, new_hash)
                return

            # 4.4 – routing bit
            next_bit = self._bit(key, key_pos)
            child_hash = current.child_1 if next_bit else current.child_0

            # 4.6 – no child → easy append leaf
            if child_hash is None:
                self._append_leaf(current, next_bit, key, key_pos, value, stack)
                return

            # 4.7 – push current node onto stack
            stack.append((current, current.hash(), int(next_bit)))

            # 4.8 – fetch child and continue
            child = self._fetch(storage_node, child_hash)
            if child is None:
                # Dangling pointer: treat as missing child
                parent, _, _ = stack[-1]
                self._append_leaf(parent, next_bit, key, key_pos, value, stack[:-1])
                return

            current = child
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
        tail_len = len(key) * 8 - (key_pos + 1)
        tail_bits, tail_len = self._bit_slice(key, key_pos + 1, tail_len)
        leaf = self._make_node(tail_bits, tail_len, value, None, None)

        old_parent_hash = parent.hash()
        
        if dir_bit:
            parent.child_1 = leaf.hash()
        else:
            parent.child_0 = leaf.hash()

        self._invalidate_hash(parent)
        new_parent_hash = parent.hash()
        if new_parent_hash != old_parent_hash:
            self.nodes.pop(old_parent_hash, None)
        self.nodes[new_parent_hash] = parent
        self._bubble(stack, new_parent_hash)


    def _split_and_insert(
        self,
        node: PatriciaNode,
        stack: List[Tuple[PatriciaNode, bytes, int]],
        key: bytes,
        key_pos: int,
        value: bytes,
    ) -> None:
        # ➊—find longest-common-prefix (lcp) as before …
        max_lcp = min(node.key_len, len(key) * 8 - key_pos)
        lcp = 0
        while lcp < max_lcp and self._bit(node.key, lcp) == self._bit(key, key_pos + lcp):
            lcp += 1

        # divergence bit values (taken **before** we mutate node.key)
        old_div_bit = self._bit(node.key, lcp)
        new_div_bit = self._bit(key, key_pos + lcp)

        # ➋—internal node that holds the common prefix
        common_bits, common_len = self._bit_slice(node.key, 0, lcp)
        internal = self._make_node(common_bits, common_len, None, None, None)

        # ➌—trim the *existing* node’s prefix **after** the divergence bit
        old_suffix_bits, old_suffix_len = self._bit_slice(
            node.key,
            lcp + 1,                       # start *after* divergence bit
            node.key_len - lcp - 1         # may be zero
        )
        old_node_hash = node.hash()

        node.key = old_suffix_bits
        node.key_len = old_suffix_len
        self._invalidate_hash(node)
        new_node_hash = node.hash()
        if new_node_hash != old_node_hash:
            self.nodes.pop(old_node_hash, None)
        self.nodes[new_node_hash] = node

        # ➍—new leaf for the key being inserted (unchanged)
        new_tail_len = len(key) * 8 - (key_pos + lcp + 1)
        new_tail_bits, _ = self._bit_slice(key, key_pos + lcp + 1, new_tail_len)
        leaf = self._make_node(new_tail_bits, new_tail_len, value, None, None)

        # ➎—hang the two children off the internal node
        if old_div_bit:
            internal.child_1 = new_node_hash
            internal.child_0 = leaf.hash()
        else:
            internal.child_0 = new_node_hash
            internal.child_1 = leaf.hash()

        # ➏—rehash up to the root (unchanged)
        self._invalidate_hash(internal)
        internal_hash = internal.hash()
        self.nodes[internal_hash] = internal

        if not stack:
            self.root_hash = internal_hash
            return

        parent, _, dir_bit = stack.pop()
        if dir_bit == 0:
            parent.child_0 = internal_hash
        else:
            parent.child_1 = internal_hash
        self._invalidate_hash(parent)
        self._bubble(stack, parent.hash())


    def _make_node(
        self,
        prefix_bits: bytes,
        prefix_len: int,
        value: Optional[bytes],
        child0: Optional[bytes],
        child1: Optional[bytes],
    ) -> PatriciaNode:
        node = PatriciaNode(prefix_len, prefix_bits, value, child0, child1)
        self.nodes[node.hash()] = node
        return node

    def _invalidate_hash(self, node: PatriciaNode) -> None:
        """Clear cached hash so next .hash() recomputes."""
        node._hash = None  # type: ignore

    def _bubble(
        self,
        stack: List[Tuple[PatriciaNode, bytes, int]],
        new_hash: bytes
    ) -> None:
        """
        Propagate updated child-hash `new_hash` up the ancestor stack,
        rebasing each parent's pointer, invalidating and re-hashing.
        """
        while stack:
            parent, old_hash, dir_bit = stack.pop()

            if dir_bit == 0:
                parent.child_0 = new_hash
            else:
                parent.child_1 = new_hash

            self._invalidate_hash(parent)
            new_hash = parent.hash()
            if new_hash != old_hash:
                self.nodes.pop(old_hash, None)
            self.nodes[new_hash] = parent
            
        self.root_hash = new_hash


    def _bit_slice(
        self,
        buf: bytes,
        start_bit: int,
        length: int
    ) -> tuple[bytes, int]:
        """
        Extract `length` bits from `buf` starting at `start_bit` (MSB-first),
        returning (bytes, bit_len) with zero-padding.
        """
        if length == 0:
            return b"", 0

        total = int.from_bytes(buf, "big")
        bits_in_buf = len(buf) * 8

        # shift so slice ends at LSB
        shift = bits_in_buf - (start_bit + length)
        slice_int = (total >> shift) & ((1 << length) - 1)

        # left-align to MSB of first byte
        pad = (8 - (length % 8)) % 8
        slice_int <<= pad
        byte_len = (length + 7) // 8
        return slice_int.to_bytes(byte_len, "big"), length
