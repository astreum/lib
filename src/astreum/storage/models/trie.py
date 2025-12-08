from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from .atom import Atom, AtomKind, ZERO32

if TYPE_CHECKING:
    from .._node import Node

class TrieNode:
    """
    A node in a compressed-key Binary Radix Tree.

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
        Compute and cache the canonical hash for this node (its type-atom id).
        """
        if self._hash is None:
            head_hash, _ = self._render_atoms()
            self._hash = head_hash
        return self._hash

    def to_bytes(self) -> bytes:
        """
        Serialize for hashing: key_len (u16 big-endian) + key payload +
        child_0 (or ZERO32) + child_1 (or ZERO32) + value.
        """
        key_len_bytes = self.key_len.to_bytes(2, "big", signed=False)
        child0 = self.child_0 or ZERO32
        child1 = self.child_1 or ZERO32
        value = self.value or b""
        return key_len_bytes + self.key + child0 + child1 + value
    
    def _render_atoms(self) -> Tuple[bytes, List[Atom]]:
        """
        Materialise this node with the canonical atom layout used by the
        storage layer: a leading SYMBOL atom with payload ``b"trie"`` whose
        ``next`` pointer links to four BYTES atoms containing, in order:
        key (len byte + key payload), child_0 hash, child_1 hash, value bytes.
        Returns the top atom hash and the emitted atoms.
        """
        entries: List[bytes] = [
            self.key_len.to_bytes(2, "big", signed=False) + self.key,
            self.child_0 or ZERO32,
            self.child_1 or ZERO32,
            self.value or b"",
        ]

        data_atoms: List[Atom] = []
        next_hash = ZERO32
        for payload in reversed(entries):
            atom = Atom(data=payload, next_id=next_hash, kind=AtomKind.BYTES)
            data_atoms.append(atom)
            next_hash = atom.object_id()

        data_atoms.reverse()

        type_atom = Atom(data=b"trie", next_id=next_hash, kind=AtomKind.SYMBOL)

        atoms = data_atoms + [type_atom]
        return type_atom.object_id(), atoms

    def to_atoms(self) -> Tuple[bytes, List[Atom]]:
        head_hash, atoms = self._render_atoms()
        self._hash = head_hash
        return head_hash, atoms

    @classmethod
    def from_atoms(
        cls,
        node: "Node",
        head_hash: bytes,
    ) -> "TrieNode":
        """
        Reconstruct a node from the atom chain rooted at `head_hash`, using the
        supplied `node` instance to resolve atom object ids.
        """
        if head_hash == ZERO32:
            raise ValueError("empty atom chain for Patricia node")

        atom_chain = node.get_atom_list_from_storage(head_hash)
        if atom_chain is None or len(atom_chain) != 5:
            raise ValueError("malformed Patricia atom chain")

        type_atom, key_atom, child0_atom, child1_atom, value_atom = atom_chain

        if type_atom.kind is not AtomKind.SYMBOL:
            raise ValueError("malformed Patricia node (type atom kind)")
        if type_atom.data != b"trie":
            raise ValueError("not a Patricia node (type mismatch)")

        for detail in (key_atom, child0_atom, child1_atom, value_atom):
            if detail.kind is not AtomKind.BYTES:
                raise ValueError("Patricia node detail atoms must be bytes")

        key_entry = key_atom.data
        if len(key_entry) < 2:
            raise ValueError("missing key entry while decoding Patricia node")
        key_len = int.from_bytes(key_entry[:2], "big", signed=False)
        key = key_entry[2:]
        child_0 = child0_atom.data if child0_atom.data != ZERO32 else None
        child_1 = child1_atom.data if child1_atom.data != ZERO32 else None
        value = value_atom.data

        return cls(key_len=key_len, key=key, value=value, child_0=child_0, child_1=child_1)

class Trie:
    """
    A compressed-key Binary Radix Tree supporting get and put.
    """

    def __init__(
        self,
        root_hash: Optional[bytes] = None,
    ) -> None:
        """
        :param root_hash: optional hash of existing root node
        """
        self.nodes: Dict[bytes, TrieNode] = {}
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

    def _fetch(self, storage_node: "Node", h: bytes) -> Optional[TrieNode]:
        """
        Fetch a node by hash, consulting the in-memory cache first and falling
        back to the atom storage provided by `storage_node`.
        """
        cached = self.nodes.get(h)
        if cached is not None:
            return cached

        if storage_node.storage_get(h) is None:
            return None

        pat_node = TrieNode.from_atoms(storage_node, h)
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

    def get_all(self, storage_node: "Node") -> Dict[bytes, bytes]:
        """
        Return a mapping of every key/value pair stored in the trie.
        """
        if self.root_hash is None or self.root_hash == ZERO32:
            return {}

        def _bits_from_payload(payload: bytes, bit_length: int) -> str:
            if bit_length <= 0 or not payload:
                return ""
            bit_stream = "".join(f"{byte:08b}" for byte in payload)
            return bit_stream[:bit_length]

        def _bits_to_bytes(bit_string: str) -> bytes:
            if not bit_string:
                return b""
            pad = (8 - (len(bit_string) % 8)) % 8
            bit_string = bit_string + ("0" * pad)
            byte_len = len(bit_string) // 8
            return int(bit_string, 2).to_bytes(byte_len, "big")

        results: Dict[bytes, bytes] = {}
        stack: List[Tuple[bytes, str]] = [(self.root_hash, "")]
        visited: Set[bytes] = set()

        while stack:
            node_hash, prefix_bits = stack.pop()
            if not node_hash or node_hash == ZERO32 or node_hash in visited:
                continue
            visited.add(node_hash)

            pat_node = TrieNode.from_atoms(storage_node, node_hash)
            node_bits = _bits_from_payload(pat_node.key, pat_node.key_len)
            combined_bits = prefix_bits + node_bits

            if pat_node.value is not None:
                key_bytes = _bits_to_bytes(combined_bits)
                results[key_bytes] = pat_node.value

            if pat_node.child_0:
                stack.append((pat_node.child_0, combined_bits + "0"))
            if pat_node.child_1:
                stack.append((pat_node.child_1, combined_bits + "1"))

        return results

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
        stack: List[Tuple[TrieNode, bytes, int]] = []  # (parent, parent_hash, dir_bit)
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
        parent: TrieNode,
        dir_bit: bool,
        key: bytes,
        key_pos: int,
        value: bytes,
        stack: List[Tuple[TrieNode, bytes, int]],
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
        node: TrieNode,
        stack: List[Tuple[TrieNode, bytes, int]],
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
    ) -> TrieNode:
        node = TrieNode(prefix_len, prefix_bits, value, child0, child1)
        self.nodes[node.hash()] = node
        return node

    def _invalidate_hash(self, node: TrieNode) -> None:
        """Clear cached hash so next .hash() recomputes."""
        node._hash = None  # type: ignore

    def _bubble(
        self,
        stack: List[Tuple[TrieNode, bytes, int]],
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
