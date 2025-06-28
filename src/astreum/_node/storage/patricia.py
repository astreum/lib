import blake3
from typing import Optional, List
from .storage import Storage
import astreum.format as format format.decode, format.encode


def common_prefix_length(a: bytes, b: bytes) -> int:
    """Return the number of common prefix bytes between a and b."""
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    return i


class PatriciaNode:
    def __init__(self, key: bytes, value: Optional[bytes], children: Optional[List[bytes]] = None):
        """
        Initialize a Patricia node.
        
        :param key: A compressed part of the key.
        :param value: The stored value (if this node represents a complete key) or None.
        :param children: A list of child node hashes (bytes). The children are ordered by the first
                         byte of the child's key.
        """
        self.key = key
        self.value = value
        self.children = children if children is not None else []
        self._hash: Optional[bytes] = None

    @classmethod
    def from_bytes(cls, data: bytes) -> 'PatriciaNode':
        """
        Deserialize a PatriciaNode from its byte representation.
        
        Expected format: [key, value, children]
        where children is a list of child node hashes (bytes).
        """
        decoded = format.decode(data)
        key, value, children = decoded
        return cls(key, value, children)

    @classmethod
    def from_storage(cls, storage: Storage, hash_value: bytes) -> Optional['PatriciaNode']:
        """
        Retrieve and deserialize a PatriciaNode from storage using its hash.
        
        :param storage: The Storage instance used to retrieve the node.
        :param hash_value: The hash key under which the node is stored.
        :return: A PatriciaNode instance if found, otherwise None.
        """
        node_bytes = storage.get(hash_value)
        if node_bytes is None:
            return None
        return cls.from_bytes(node_bytes)

    def to_bytes(self) -> bytes:
        """
        Serialize the PatriciaNode into bytes using the Astreum format.
        
        Structure: [key, value, children]
        """
        return format.encode([self.key, self.value, self.children])

    def hash(self) -> bytes:
        """
        Compute (or retrieve a cached) Blake3 hash over the node's serialized bytes.
        """
        if self._hash is None:
            self._hash = blake3.blake3(self.to_bytes()).digest()
        return self._hash

    def invalidate_hash(self) -> None:
        """Clear the cached hash so that it is recomputed on next use."""
        self._hash = None


class PatriciaTrie:
    def __init__(self, storage: Storage, root_hash: Optional[bytes] = None):
        """
        Initialize a Patricia Trie.
        
        :param storage: A Storage instance for persisting nodes.
        :param root_hash: Optionally, an existing root hash. If None, the trie is empty.
        """
        self.storage = storage
        self.root_hash = root_hash

    def get(self, key: bytes) -> Optional[bytes]:
        """
        Retrieve the value associated with the given key.
        
        :param key: The key (as bytes) to search for.
        :return: The stored value if found, otherwise None.
        """
        if self.root_hash is None:
            return None
        return self._get(self.root_hash, key)

    def _get(self, node_hash: bytes, key: bytes) -> Optional[bytes]:
        node = PatriciaNode.from_storage(self.storage, node_hash)
        if node is None:
            return None

        cp_len = common_prefix_length(key, node.key)
        # If node.key completely matches the beginning of key...
        if cp_len == len(node.key):
            if cp_len == len(key):
                return node.value
            remainder = key[cp_len:]
            branch = remainder[0]
            child_hash = self._find_child(node.children, branch)
            if child_hash is None:
                return None
            return self._get(child_hash, remainder)
        return None

    def put(self, key: bytes, value: bytes) -> None:
        """
        Insert or update the key with the provided value.
        
        :param key: The key (as bytes) to insert.
        :param value: The value (as bytes) to associate with the key.
        """
        if self.root_hash is None:
            new_node = PatriciaNode(key, value, [])
            new_hash = new_node.hash()
            self.storage.put(new_hash, new_node.to_bytes())
            self.root_hash = new_hash
        else:
            self.root_hash = self._put(self.root_hash, key, value)

    def _put(self, node_hash: bytes, key: bytes, value: bytes) -> bytes:
        """
        Recursive helper for inserting or updating a key.
        
        Returns the new hash for the node that replaces the current node.
        """
        node = PatriciaNode.from_storage(self.storage, node_hash)
        if node is None:
            # Node missing: create a new leaf.
            new_node = PatriciaNode(key, value, [])
            new_hash = new_node.hash()
            self.storage.put(new_hash, new_node.to_bytes())
            return new_hash

        cp_len = common_prefix_length(key, node.key)
        len_node_key = len(node.key)
        len_key = len(key)

        # Case 1: Exact match: update the value.
        if cp_len == len_node_key and cp_len == len_key:
            node.value = value
            node.invalidate_hash()
            new_hash = node.hash()
            self.storage.put(new_hash, node.to_bytes())
            self.storage.delete(node_hash)
            return new_hash

        # Case 2: Node key is a prefix of key (descend to child).
        if cp_len == len_node_key:
            remainder = key[cp_len:]
            branch = remainder[0]
            child_hash = self._find_child(node.children, branch)
            if child_hash is not None:
                new_child_hash = self._put(child_hash, remainder, value)
                # Update the child pointer in the list.
                idx = self._find_child_index(node.children, branch)
                if idx is None:
                    raise Exception("Child not found during update.")
                node.children[idx] = new_child_hash
            else:
                # Create a new leaf for the remainder.
                new_leaf = PatriciaNode(remainder, value, [])
                new_leaf_hash = new_leaf.hash()
                self.storage.put(new_leaf_hash, new_leaf.to_bytes())
                self._insert_child(node.children, new_leaf_hash)
            node.invalidate_hash()
            new_hash = node.hash()
            self.storage.put(new_hash, node.to_bytes())
            self.storage.delete(node_hash)
            return new_hash

        # Case 3: Key is a prefix of node.key (split node).
        if cp_len == len_key and cp_len < len_node_key:
            old_suffix = node.key[cp_len:]
            node.key = old_suffix  # update node to hold only the suffix
            node.invalidate_hash()

            # Create a new branch node with the key as prefix and value.
            branch_node = PatriciaNode(key, value, [])
            # The existing node becomes a child of the branch.
            self._insert_child(branch_node.children, node.hash())
            branch_hash = branch_node.hash()
            self.storage.put(branch_hash, branch_node.to_bytes())
            self.storage.put(node.hash(), node.to_bytes())
            self.storage.delete(node_hash)
            return branch_hash

        # Case 4: Partial common prefix (split into a branch with two children).
        if cp_len < len_node_key and cp_len < len_key:
            common_prefix = key[:cp_len]
            old_suffix = node.key[cp_len:]
            new_suffix = key[cp_len:]
            branch_node = PatriciaNode(common_prefix, None, [])
            
            # Adjust the existing node.
            node.key = old_suffix
            node.invalidate_hash()
            self._insert_child(branch_node.children, node.hash())

            # Create a new leaf for the new key’s remaining portion.
            new_leaf = PatriciaNode(new_suffix, value, [])
            new_leaf_hash = new_leaf.hash()
            self.storage.put(new_leaf_hash, new_leaf.to_bytes())
            self._insert_child(branch_node.children, new_leaf_hash)

            branch_hash = branch_node.hash()
            self.storage.put(branch_hash, branch_node.to_bytes())
            self.storage.put(node.hash(), node.to_bytes())
            self.storage.delete(node_hash)
            return branch_hash

        raise Exception("Unhandled case in PatriciaTrie.put")

    def _find_child(self, children: List[bytes], branch: int) -> Optional[bytes]:
        """
        Perform a binary search over the ordered children list to find the child hash whose
        branch (first byte of its key) equals the target branch.
        """
        lo = 0
        hi = len(children)
        while lo < hi:
            mid = (lo + hi) // 2
            child_hash = children[mid]
            child_node = PatriciaNode.from_storage(self.storage, child_hash)
            if child_node is None or not child_node.key:
                raise Exception("Child node missing or has empty key.")
            child_branch = child_node.key[0]
            if child_branch == branch:
                return child_hash
            elif child_branch < branch:
                lo = mid + 1
            else:
                hi = mid
        return None

    def _find_child_index(self, children: List[bytes], branch: int) -> Optional[int]:
        """
        Similar to _find_child but returns the index in the list.
        """
        lo = 0
        hi = len(children)
        while lo < hi:
            mid = (lo + hi) // 2
            child_hash = children[mid]
            child_node = PatriciaNode.from_storage(self.storage, child_hash)
            if child_node is None or not child_node.key:
                raise Exception("Child node missing or has empty key.")
            child_branch = child_node.key[0]
            if child_branch == branch:
                return mid
            elif child_branch < branch:
                lo = mid + 1
            else:
                hi = mid
        return None

    def _insert_child(self, children: List[bytes], new_child_hash: bytes) -> None:
        """
        Insert a new child hash into the ordered children list.
        """
        new_child_node = PatriciaNode.from_storage(self.storage, new_child_hash)
        if new_child_node is None or not new_child_node.key:
            raise Exception("New child node missing or has empty key.")
        new_branch = new_child_node.key[0]
        lo = 0
        hi = len(children)
        while lo < hi:
            mid = (lo + hi) // 2
            child_hash = children[mid]
            child_node = PatriciaNode.from_storage(self.storage, child_hash)
            if child_node is None or not child_node.key:
                raise Exception("Child node missing or has empty key.")
            child_branch = child_node.key[0]
            if child_branch < new_branch:
                lo = mid + 1
            else:
                hi = mid
        children.insert(lo, new_child_hash)
