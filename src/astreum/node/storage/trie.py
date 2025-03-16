from astreum.utils.bytes_format import encode, decode
from astreum.utils.hash import hash_data
from typing import Optional, List
from ..storage import Storage


class Trie:
    def __init__(self, root: TrieNode, storage: Storage):
        self.root = root
        self.storage = storage

    def insert(self, key: bytes, data: bytes):
        self.root = self._insert(self.root, key, data)

    def _insert(self, node: TrieNode, key: bytes, data: bytes) -> TrieNode:
        if node is None:
            return TrieNode(key, data)
        if key < node.key:
            node.children = self._insert(node.children, key, data)
        elif key > node.key:
            node.children = self._insert(node.children, key, data)
        else:
            node.data = data
        return node

    def lookup(self, key: bytes) -> bytes:
        """
        Look up a key in the trie.
        
        Args:
            key: The key to look up
            
        Returns:
            The data associated with the key, or None if not found
        """
        return self._lookup(self.root, key)

    def _lookup(self, node: Optional[TrieNode], key: bytes) -> bytes:
        """
        Recursive helper for looking up a key in the trie.
        
        Args:
            node: The current node being examined
            key: The key to look up
            
        Returns:
            The data associated with the key, or None if not found
        """
        if node is None:
            return None
            
        # If we found an exact match, return the data
        if node.key == key:
            return node.data
            
        # Make sure node has a storage reference
        if node.storage is None:
            node.storage = self.storage
            
        # Use child_lookup to find the most promising child
        child_node = node.child_lookup(key)
        if child_node is None:
            return None
            
        # Create and traverse to the child node
        child_node = TrieNode.from_bytes(child_data, self.storage)
        return self._lookup(child_node, key)

class TrieNode:
    """
    A node in a trie.

    Attributes:
        key: The key of the node
        data: The data stored in the node
        children: The children of the node
        storage: Reference to storage service (not serialized)
    """
    def __init__(self, key: bytes, data: bytes = None, children: bytes = None, storage = None):
        """
        Initialize a new TrieNode.
        
        Args:
            key: The key of the node
            data: The data stored in the node
            children: a byte string of children hashes each are 32 bytes long
            storage: Storage instance for retrieving child nodes (not serialized)
        """
        self.key = key
        self.data = data
        self.children = children
        self.storage = storage

    def to_bytes(self) -> bytes:
        """Serialize the node data (excluding storage reference)"""
        return encode([self.key, self.data, self.children])

    @classmethod
    def from_bytes(cls, data: bytes, storage = None) -> 'TrieNode':
        """
        Deserialize node data and optionally attach a storage reference.
        
        Args:
            data: The serialized node data
            storage: Optional storage instance to attach to the node
        
        Returns:
            A new TrieNode instance
        """
        key, data, children = decode(data)
        return TrieNode(key, data, children, storage)

    def hash(self) -> bytes:
        return hash_data(self.to_bytes())

    def child_lookup(self, key: bytes) -> Optional[TrieNode]:
        """
        Does a binary lookup of the keys in the children of this node.
        Uses storage to look up children and finds a starting match for the key.
        """
        if self.children is None or self.storage is None:
            return None
        
        # Parse children bytes into a list of 32-byte hashes
        children_hashes = []
        for i in range(0, len(self.children), 32):
            if i + 32 <= len(self.children):
                children_hashes.append(self.children[i:i+32])
        
        # Look up each child in storage and compare keys
        for child_hash in children_hashes:
            # Get child node data from storage
            child_data = self.storage.get(child_hash)
            if child_data is None:
                continue  # Skip if not found in storage
            
            # Deserialize the child node
            child_node = TrieNode.from_bytes(child_data, self.storage)
            
            # Check if this child's key is a prefix of the lookup key
            # or if the lookup key is a prefix of this child's key
            min_len = min(len(child_node.key), len(key))
            if child_node.key[:min_len] == key[:min_len]:
                return child_node
        
        return None
