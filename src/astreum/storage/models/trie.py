from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING, Union

from ...machine.models.expression import Expr, NIL, ZERO32, link, int_, bytes_

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
        value: Optional[Union[Expr, bytes]],
        child_0: Optional[bytes],
        child_1: Optional[bytes]
    ):
        self.key_len = key_len
        self.key = key
        self.value = value
        self.child_0 = child_0
        self.child_1 = child_1
        self._hash: Optional[bytes] = None
        self._expr: Optional["Expr"] = None

    def hash(self) -> bytes:
        """Compute and cache the canonical hash for this node."""
        if self._hash is None:
            self._hash = self.expr().hash()
        return self._hash

    def clone(self) -> "TrieNode":
        cloned = TrieNode(
            key_len=self.key_len,
            key=bytes(self.key),
            value=None if self.value is None else (
                bytes(self.value) if isinstance(self.value, bytes) else self.value
            ),
            child_0=None if self.child_0 is None else bytes(self.child_0),
            child_1=None if self.child_1 is None else bytes(self.child_1),
        )
        cloned._hash = None if self._hash is None else bytes(self._hash)
        cloned._expr = self._expr
        return cloned

    def to_expr(self) -> Expr:
        from ...machine.models.expression import Expr, NIL

        # value (innermost)
        if self.value is None:
            expr = NIL
        elif isinstance(self.value, bytes):
            expr = Expr("link", head_hash=self.value, tail=NIL)
        else:
            expr = link(self.value, NIL)

        # child_1
        expr = Expr("link", head_hash=self.child_1, tail=expr) if self.child_1 else link(NIL, expr)
        # child_0
        expr = Expr("link", head_hash=self.child_0, tail=expr) if self.child_0 else link(NIL, expr)
        # key
        expr = link(bytes_(self.key), expr)
        # key_len (outermost)
        expr = link(int_(self.key_len), expr)
        return expr

    def expr(self) -> "Expr":
        """Cached accessor: builds the Expr tree once and caches it."""
        if self._expr is None:
            self._expr = self.to_expr()
        return self._expr

    @classmethod
    def from_storage(
        cls,
        node: "Node",
        head_hash: bytes,
    ) -> "TrieNode":
        """Reconstruct a node from the Expr.Link chain rooted at `head_hash`.

        Follows the same pattern as Block.from_storage and Receipt.from_storage.
        """
        from ...machine.models.expression import Expr, resolve_list_exprs

        if head_hash == ZERO32:
            raise ValueError("empty expr chain for Patricia node")

        expr = node.get_expr_list(head_hash)
        if expr is None:
            raise ValueError("could not retrieve Patricia node expr from storage")

        elements, missed = resolve_list_exprs(node, expr)
        if missed:
            raise ValueError(
                f"unresolved hashes in Patricia node expr (missed={[h.hex()[:8] for h in missed]})"
            )
        if len(elements) != 5:
            raise ValueError(
                f"malformed Patricia node expr length (got={len(elements)}, expected=5)"
            )

        key_len_expr, key_expr, child_0_expr, child_1_expr, value_expr = elements

        if not key_len_expr._tag == "int":
            raise ValueError("Patricia node key_len must be Int")
        key_len = key_len_expr.value

        if not key_expr._tag == "bytes":
            raise ValueError("Patricia node key must be Bytes")
        key = key_expr.value

        child_0: Optional[bytes] = None
        if child_0_expr._tag == "link" and child_0_expr is not NIL:
            child_0 = child_0_expr.hash()

        child_1: Optional[bytes] = None
        if child_1_expr._tag == "link" and child_1_expr is not NIL:
            child_1 = child_1_expr.hash()

        value: Optional[Expr] = None
        if value_expr is not NIL:
            value = value_expr

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

    def clone(self) -> "Trie":
        cloned = Trie(root_hash=None if self.root_hash is None else bytes(self.root_hash))
        cloned.nodes = {
            bytes(node_hash): node.clone()
            for node_hash, node in self.nodes.items()
        }
        return cloned

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
        cached = self.nodes.get(h)
        if cached is not None:
            return cached

        if storage_node.get_expr(expr_id=h) is None:
            return None

        pat_node = TrieNode.from_storage(storage_node, h)
        self.nodes[h] = pat_node
        return pat_node

    def get(self, storage_node: "Node", key: bytes) -> Optional[Expr]:
        """
        Return the stored value for `key`, or None if absent.
        """
        # TODO: raise on unresolved backing trie atoms instead of returning None.
        # Consensus callers need to distinguish proven absence from network misses.
        # Empty trie?
        if self.root_hash is None or self.root_hash == ZERO32:
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
                val = current.value
                if val is None:
                    return None
                if isinstance(val, bytes):
                    return storage_node.get_expr(val)
                return val

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

    def get_all(self, storage_node: "Node") -> Dict[bytes, Expr]:
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

        results: Dict[bytes, Expr] = {}
        stack: List[Tuple[bytes, str]] = [(self.root_hash, "")]
        visited: Set[bytes] = set()

        while stack:
            node_hash, prefix_bits = stack.pop()
            if not node_hash or node_hash == ZERO32 or node_hash in visited:
                continue
            visited.add(node_hash)

            pat_node = TrieNode.from_storage(storage_node, node_hash)
            self.nodes[node_hash] = pat_node

            node_bits = _bits_from_payload(pat_node.key, pat_node.key_len)
            combined_bits = prefix_bits + node_bits

            if pat_node.value is not None:
                key_bytes = _bits_to_bytes(combined_bits)
                val = pat_node.value
                if isinstance(val, bytes):
                    results[key_bytes] = storage_node.get_expr(val)
                else:
                    results[key_bytes] = val

            if pat_node.child_0:
                stack.append((pat_node.child_0, combined_bits + "0"))
            if pat_node.child_1:
                stack.append((pat_node.child_1, combined_bits + "1"))

        return results

    def put(self, storage_node: "Node", key: bytes, value: Union[Expr, bytes]) -> None:
        """
        Insert or update `key` with `value` in-place.

        `value` may be a concrete `Expr` or a `bytes` expr_id/hash.
        """
        total_bits = len(key) * 8

        # S1 – Empty trie → create root leaf
        if self.root_hash is None or self.root_hash == ZERO32:
            leaf = self._make_node(key, total_bits, value, None, None)
            leaf_hash = leaf.hash()
            self.nodes[leaf_hash] = leaf
            self.root_hash = leaf_hash
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
                # TODO: raise on unresolved backing trie atoms instead of appending.
                # Treating a network miss as an absent child can corrupt state.
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
        value: Union[Expr, bytes],
        stack: List[Tuple[TrieNode, bytes, int]],
    ) -> None:
        tail_len = len(key) * 8 - (key_pos + 1)
        tail_bits, tail_len = self._bit_slice(key, key_pos + 1, tail_len)
        leaf = self._make_node(tail_bits, tail_len, value, None, None)
        leaf_hash = leaf.hash()
        self.nodes[leaf_hash] = leaf

        old_parent_hash = parent.hash()
        
        if dir_bit:
            parent.child_1 = leaf_hash
        else:
            parent.child_0 = leaf_hash

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
        value: Union[Expr, bytes],
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
        leaf_hash = leaf.hash()
        self.nodes[leaf_hash] = leaf

        # ➎—hang the two children off the internal node
        if old_div_bit:
            internal.child_1 = new_node_hash
            internal.child_0 = leaf_hash
        else:
            internal.child_0 = new_node_hash
            internal.child_1 = leaf_hash

        # ➏—rehash up to the root (unchanged)
        self._invalidate_hash(internal)
        internal_hash = internal.hash()
        self.nodes[internal_hash] = internal

        if not stack:
            self.root_hash = internal_hash
            return

        parent, old_hash, dir_bit = stack.pop()
        if dir_bit == 0:
            parent.child_0 = internal_hash
        else:
            parent.child_1 = internal_hash
        self._invalidate_hash(parent)
        new_parent_hash = parent.hash()
        if new_parent_hash != old_hash:
            self.nodes.pop(old_hash, None)
        self.nodes[new_parent_hash] = parent
        self._bubble(stack, new_parent_hash)


    def _make_node(
        self,
        prefix_bits: bytes,
        prefix_len: int,
        value: Optional[Union[Expr, bytes]],
        child0: Optional[bytes],
        child1: Optional[bytes],
    ) -> TrieNode:
        node = TrieNode(prefix_len, prefix_bits, value, child0, child1)
        return node

    def _invalidate_hash(self, node: TrieNode) -> None:
        """Clear cached hash and expr so next access recomputes."""
        node._hash = None  # type: ignore
        node._expr = None

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
