"""
General purpose Merkle tree implementation for the Astreum blockchain.

This module provides a flexible Merkle tree implementation that can be used
across the Astreum codebase, integrated with the existing storage system.
Supports efficient binary search and resolvers for querying data.
"""

import threading
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Set, Any, Callable, Union, TypeVar, Generic
from enum import Enum, auto

from ..utils import hash_data


class MerkleNodeType(Enum):
    """Types of Merkle tree nodes."""
    LEAF = auto()    # Contains actual data
    BRANCH = auto()  # Internal node with children


@dataclass
class MerkleNode:
    """
    Represents a node in the Merkle tree.
    
    Attributes:
        node_type: Type of the node (LEAF or BRANCH)
        hash: The hash of this node
        data: The data stored in this node (for leaf nodes)
        left_child: Hash of the left child (for branch nodes)
        right_child: Hash of the right child (for branch nodes)
    """
    node_type: MerkleNodeType
    hash: bytes
    data: Optional[bytes] = None
    left_child: Optional[bytes] = None
    right_child: Optional[bytes] = None
    
    def serialize(self) -> bytes:
        """Serialize the node to bytes for storage."""
        if self.node_type == MerkleNodeType.LEAF:
            # Format: [1-byte type][data]
            type_byte = b'\x00'
            return type_byte + self.data
        else:  # BRANCH
            # Format: [1-byte type][32-byte left child hash][32-byte right child hash]
            type_byte = b'\x01'
            return type_byte + self.left_child + self.right_child
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'MerkleNode':
        """Deserialize bytes into a MerkleNode object."""
        type_byte = data[0]
        if type_byte == 0:  # LEAF
            node_data = data[1:]
            node_hash = hash_data(data)
            return cls(
                node_type=MerkleNodeType.LEAF,
                hash=node_hash,
                data=node_data
            )
        elif type_byte == 1:  # BRANCH
            left_child = data[1:33]
            right_child = data[33:65]
            node_hash = hash_data(data)
            return cls(
                node_type=MerkleNodeType.BRANCH,
                hash=node_hash,
                left_child=left_child,
                right_child=right_child
            )
        else:
            raise ValueError(f"Unknown node type: {type_byte}")


@dataclass
class MerkleProof:
    """
    Represents a Merkle inclusion proof.
    
    A proof consists of the original data and a series of sibling hashes
    that allow verification without having the entire tree.
    
    Attributes:
        leaf_hash: Hash of the leaf node being proven
        siblings: List of sibling hashes needed for verification
        path: Bit array indicating left (0) or right (1) at each level
    """
    leaf_hash: bytes
    siblings: List[bytes]
    path: List[bool]  # False=left, True=right
    
    def verify(self, root_hash: bytes) -> bool:
        """
        Verify this proof against a root hash.
        
        Args:
            root_hash: The expected root hash of the Merkle tree
            
        Returns:
            True if the proof is valid, False otherwise
        """
        if not self.siblings:
            # Special case: single node tree
            return self.leaf_hash == root_hash
            
        current_hash = self.leaf_hash
        
        for i, sibling in enumerate(self.siblings):
            # At each level, hash the current hash with the sibling
            if self.path[i]:  # right
                current_hash = hash_data(b'\x01' + sibling + current_hash)
            else:  # left
                current_hash = hash_data(b'\x01' + current_hash + sibling)
        
        return current_hash == root_hash
    
    def serialize(self) -> bytes:
        """Serialize the proof to bytes."""
        # Convert path to bytes (1 bit per boolean)
        path_bytes = bytearray()
        for i in range(0, len(self.path), 8):
            byte = 0
            for j in range(8):
                if i + j < len(self.path) and self.path[i + j]:
                    byte |= (1 << j)
            path_bytes.append(byte)
        
        # Format: [32-byte leaf hash][1-byte path length][path bits][siblings...]
        result = self.leaf_hash + len(self.path).to_bytes(1, 'big') + bytes(path_bytes)
        
        for sibling in self.siblings:
            result += sibling
            
        return result
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'MerkleProof':
        """Deserialize bytes into a MerkleProof object."""
        leaf_hash = data[:32]
        path_length = data[32]
        
        # Path bytes length (rounded up to nearest byte)
        path_bytes_length = (path_length + 7) // 8
        path_bytes = data[33:33+path_bytes_length]
        
        # Convert path bytes to boolean list
        path = []
        for i in range(path_length):
            byte_index = i // 8
            bit_index = i % 8
            if byte_index < len(path_bytes):
                path.append(bool(path_bytes[byte_index] & (1 << bit_index)))
            else:
                path.append(False)
        
        # Calculate number of siblings from path length
        siblings = []
        siblings_offset = 33 + path_bytes_length
        for i in range(path_length):
            if siblings_offset + 32 <= len(data):
                siblings.append(data[siblings_offset:siblings_offset+32])
                siblings_offset += 32
        
        return cls(leaf_hash=leaf_hash, siblings=siblings, path=path)


T = TypeVar('T')


def find_first(storage, root_hash: bytes, predicate: Callable[[bytes], bool]) -> Optional[bytes]:
    """
    Find the first leaf node that matches the predicate.
    
    Args:
        storage: The storage instance
        root_hash: The Merkle tree root hash
        predicate: Function that takes leaf data and returns True/False
        
    Returns:
        The data of the first matching leaf node, or None if not found
    """
    node = _get_node(storage, root_hash)
    if not node:
        return None
        
    if node.node_type == MerkleNodeType.LEAF:
        if predicate(node.data):
            return node.data
        return None
        
    # Recursively search through branch nodes, left first
    left_result = find_first(storage, node.left_child, predicate)
    if left_result:
        return left_result
        
    right_result = find_first(storage, node.right_child, predicate)
    return right_result


def find_all(storage, root_hash: bytes, predicate: Callable[[bytes], bool]) -> List[bytes]:
    """
    Find all leaf nodes that match the predicate.
    
    Args:
        storage: The storage instance
        root_hash: The Merkle tree root hash
        predicate: Function that takes leaf data and returns True/False
        
    Returns:
        List of data from all matching leaf nodes
    """
    results = []
    _find_all_recursive(storage, root_hash, predicate, results)
    return results


def _find_all_recursive(storage, node_hash: bytes, predicate: Callable[[bytes], bool], 
                      results: List[bytes]) -> None:
    """
    Recursively find all leaf nodes that match the predicate.
    
    Args:
        storage: The storage instance
        node_hash: The current node hash
        predicate: Function that takes leaf data and returns True/False
        results: List to collect matching leaf data
    """
    node = _get_node(storage, node_hash)
    if not node:
        return
        
    if node.node_type == MerkleNodeType.LEAF:
        if predicate(node.data):
            results.append(node.data)
        return
        
    # Branch node, recursively search both children
    _find_all_recursive(storage, node.left_child, predicate, results)
    _find_all_recursive(storage, node.right_child, predicate, results)


def map(storage, root_hash: bytes, transform: Callable[[bytes], T]) -> List[T]:
    """
    Apply a transform function to all leaf nodes and return the results.
    
    Args:
        storage: The storage instance
        root_hash: The Merkle tree root hash
        transform: Function that takes leaf data and returns transformed value
        
    Returns:
        List of transformed values from all leaf nodes
    """
    results = []
    _map_recursive(storage, root_hash, transform, results)
    return results


def _map_recursive(storage, node_hash: bytes, transform: Callable[[bytes], T], 
                 results: List[T]) -> None:
    """
    Recursively apply a transform function to all leaf nodes.
    
    Args:
        storage: The storage instance
        node_hash: The current node hash
        transform: Function that takes leaf data and returns transformed value
        results: List to collect transformed values
    """
    node = _get_node(storage, node_hash)
    if not node:
        return
        
    if node.node_type == MerkleNodeType.LEAF:
        results.append(transform(node.data))
        return
        
    # Branch node, recursively apply to both children
    _map_recursive(storage, node.left_child, transform, results)
    _map_recursive(storage, node.right_child, transform, results)


def binary_search(storage, root_hash: bytes, compare: Callable[[bytes], int]) -> Optional[bytes]:
    """
    Perform a binary search on a sorted Merkle tree.
    
    The tree must be sorted for this to work correctly. The compare function
    should return:
    -  0 if the data matches the target
    -  1 if the data is less than the target
    - -1 if the data is greater than the target
    
    Args:
        storage: The storage instance
        root_hash: The Merkle tree root hash
        compare: Function that takes data and returns -1, 0, or 1
        
    Returns:
        The matching data if found, None otherwise
    """
    return _binary_search_recursive(storage, root_hash, compare)


def _binary_search_recursive(storage, node_hash: bytes, 
                           compare: Callable[[bytes], int]) -> Optional[bytes]:
    """
    Recursively perform a binary search on a sorted Merkle tree.
    
    Args:
        storage: The storage instance
        node_hash: The current node hash
        compare: Comparison function
        
    Returns:
        The matching data if found, None otherwise
    """
    node = _get_node(storage, node_hash)
    if not node:
        return None
        
    if node.node_type == MerkleNodeType.LEAF:
        # Leaf node, compare the data
        comparison = compare(node.data)
        if comparison == 0:
            return node.data
        return None
        
    # For a branch node, we need to decide which side to search
    # In a sorted tree, leftmost leaf < all leaves in right subtree
    # So we check the rightmost leaf in the left subtree
    leftmost_leaf = _find_rightmost_leaf(storage, node.left_child)
    if not leftmost_leaf:
        # If left subtree is empty, search right subtree
        return _binary_search_recursive(storage, node.right_child, compare)
        
    comparison = compare(leftmost_leaf)
    
    if comparison >= 0:
        # Target <= leftmost_leaf, search left subtree
        return _binary_search_recursive(storage, node.left_child, compare)
    else:
        # Target > leftmost_leaf, search right subtree
        return _binary_search_recursive(storage, node.right_child, compare)


def _find_rightmost_leaf(storage, node_hash: bytes) -> Optional[bytes]:
    """
    Find the rightmost leaf in a subtree.
    
    Args:
        storage: The storage instance
        node_hash: The subtree root hash
        
    Returns:
        Data of the rightmost leaf, or None if the tree is empty
    """
    node = _get_node(storage, node_hash)
    if not node:
        return None
        
    if node.node_type == MerkleNodeType.LEAF:
        return node.data
        
    # Branch node, prioritize right
    right_result = _find_rightmost_leaf(storage, node.right_child)
    if right_result:
        return right_result
        
    # No right leaf, try left
    return _find_rightmost_leaf(storage, node.left_child)


def _get_node(storage, node_hash: bytes) -> Optional[MerkleNode]:
    """
    Get a node from storage.
    
    Args:
        storage: The storage instance
        node_hash: The node hash
        
    Returns:
        The MerkleNode, or None if not found
    """
    node_data = storage.get(node_hash)
    if not node_data:
        return None
    return MerkleNode.deserialize(node_data)


class MerkleTree:
    """
    A general purpose Merkle tree implementation.
    
    This class builds and manages a Merkle tree, with support for
    generating and verifying inclusion proofs. It integrates with
    the node's storage system for persistent trees.
    """
    def __init__(self, storage=None):
        """
        Initialize a new Merkle tree.
        
        Args:
            storage: The storage object to use for persisting nodes
        """
        self.storage = storage
        self.root_hash = None
        self.nodes = {}  # In-memory cache of nodes
        self.lock = threading.Lock()
    
    def add(self, data: Union[bytes, List[bytes]]) -> bytes:
        """
        Add data to the Merkle tree and return the root hash.
        
        If a list is provided, a balanced tree is built from all items.
        If a single item is provided, it's added to the existing tree.
        
        Args:
            data: The data to add (single bytes object or list of bytes)
            
        Returns:
            The root hash of the Merkle tree after adding the data
        """
        with self.lock:
            if isinstance(data, list):
                return self._build_tree(data)
            elif isinstance(data, bytes):
                if self.root_hash is None:
                    # First leaf
                    return self._build_tree([data])
                else:
                    # Add to existing tree
                    return self._add_leaf(data)
            else:
                raise TypeError("Data must be bytes or list of bytes")
    
    def add_sorted(self, data: List[bytes]) -> bytes:
        """
        Add a sorted list of data to create a balanced, ordered Merkle tree.
        
        This is particularly useful for binary search operations.
        
        Args:
            data: Sorted list of byte arrays
            
        Returns:
            The root hash of the Merkle tree
        """
        with self.lock:
            return self._build_tree(sorted(data))
    
    def _build_tree(self, items: List[bytes]) -> bytes:
        """
        Build a balanced Merkle tree from a list of items.
        
        Args:
            items: List of byte arrays to include in the tree
            
        Returns:
            The root hash of the new tree
        """
        if not items:
            return None
            
        # Create leaf nodes
        leaf_nodes = []
        for item in items:
            leaf_node = MerkleNode(
                node_type=MerkleNodeType.LEAF,
                hash=hash_data(b'\x00' + item),
                data=item
            )
            self.nodes[leaf_node.hash] = leaf_node
            if self.storage:
                self.storage.put(leaf_node.hash, leaf_node.serialize())
            leaf_nodes.append(leaf_node)
        
        # Build tree bottom-up
        return self._build_tree_level(leaf_nodes)
    
    def _build_tree_level(self, nodes: List[MerkleNode]) -> bytes:
        """
        Build a tree level by pairing nodes and creating parent nodes.
        
        Args:
            nodes: List of nodes at the current level
            
        Returns:
            The root hash (if we've reached the root) or None
        """
        if not nodes:
            return None
            
        if len(nodes) == 1:
            # We've reached the root
            self.root_hash = nodes[0].hash
            return self.root_hash
            
        # Pair up nodes to create the next level
        next_level = []
        
        for i in range(0, len(nodes), 2):
            if i + 1 < len(nodes):
                # Create a branch node with two children
                branch_node = MerkleNode(
                    node_type=MerkleNodeType.BRANCH,
                    hash=hash_data(b'\x01' + nodes[i].hash + nodes[i+1].hash),
                    left_child=nodes[i].hash,
                    right_child=nodes[i+1].hash
                )
            else:
                # Odd number of nodes, duplicate the last one
                branch_node = MerkleNode(
                    node_type=MerkleNodeType.BRANCH,
                    hash=hash_data(b'\x01' + nodes[i].hash + nodes[i].hash),
                    left_child=nodes[i].hash,
                    right_child=nodes[i].hash
                )
            
            self.nodes[branch_node.hash] = branch_node
            if self.storage:
                self.storage.put(branch_node.hash, branch_node.serialize())
            next_level.append(branch_node)
        
        # Continue building up the tree
        return self._build_tree_level(next_level)
    
    def _add_leaf(self, data: bytes) -> bytes:
        """
        Add a single leaf to an existing tree.
        
        This is more complex and requires tree restructuring.
        For now, we'll rebuild the tree with the new item.
        A more efficient implementation would be to track all 
        leaves and only rebuild the affected branches.
        
        Args:
            data: The data to add
            
        Returns:
            The new root hash
        """
        # Get all existing leaves
        leaves = self._get_all_leaves()
        
        # Add the new leaf
        leaves.append(data)
        
        # Rebuild the tree
        return self._build_tree(leaves)
    
    def _get_all_leaves(self) -> List[bytes]:
        """
        Get all leaf data from the current tree.
        
        Returns:
            List of leaf data
        """
        if not self.root_hash:
            return []
            
        leaves = []
        self._collect_leaves(self.root_hash, leaves)
        return leaves
    
    def _collect_leaves(self, node_hash: bytes, leaves: List[bytes]) -> None:
        """
        Recursively collect leaf data starting from the given node.
        
        Args:
            node_hash: Hash of the starting node
            leaves: List to collect leaf data
        """
        # Get the node
        node = self._get_node(node_hash)
        if not node:
            return
            
        if node.node_type == MerkleNodeType.LEAF:
            leaves.append(node.data)
        elif node.node_type == MerkleNodeType.BRANCH:
            self._collect_leaves(node.left_child, leaves)
            # Only collect from right child if it's different from left
            if node.right_child != node.left_child:
                self._collect_leaves(node.right_child, leaves)
    
    def _get_node(self, node_hash: bytes) -> Optional[MerkleNode]:
        """
        Get a node by its hash, from memory or storage.
        
        Args:
            node_hash: The hash of the node to get
            
        Returns:
            The node if found, None otherwise
        """
        # Check memory cache first
        if node_hash in self.nodes:
            return self.nodes[node_hash]
            
        # Then check storage if available
        if self.storage:
            node_data = self.storage.get(node_hash)
            if node_data:
                node = MerkleNode.deserialize(node_data)
                self.nodes[node_hash] = node
                return node
                
        return None
    
    def generate_proof(self, data: bytes) -> Optional[MerkleProof]:
        """
        Generate a Merkle proof for the given data.
        
        Args:
            data: The data to generate a proof for
            
        Returns:
            A MerkleProof object if the data is in the tree, None otherwise
        """
        if not self.root_hash:
            return None
            
        # Find the leaf hash for this data
        leaf_hash = hash_data(b'\x00' + data)
        
        # Find path from root to leaf
        path = []
        siblings = []
        
        if self._build_proof(self.root_hash, leaf_hash, path, siblings):
            return MerkleProof(leaf_hash=leaf_hash, siblings=siblings, path=path)
        else:
            return None
    
    def _build_proof(self, current_hash: bytes, target_hash: bytes, 
                    path: List[bool], siblings: List[bytes]) -> bool:
        """
        Recursively build a proof from the current node to the target leaf.
        
        Args:
            current_hash: Hash of the current node
            target_hash: Hash of the target leaf
            path: List to collect path directions (left=False, right=True)
            siblings: List to collect sibling hashes
            
        Returns:
            True if the path to the target was found, False otherwise
        """
        if current_hash == target_hash:
            # Found the target
            return True
            
        node = self._get_node(current_hash)
        if not node or node.node_type != MerkleNodeType.BRANCH:
            # Not a branch node or not found
            return False
            
        # Try left branch
        left_result = self._build_proof(node.left_child, target_hash, path, siblings)
        if left_result:
            path.append(False)  # Left direction
            siblings.append(node.right_child)
            return True
            
        # Try right branch
        right_result = self._build_proof(node.right_child, target_hash, path, siblings)
        if right_result:
            path.append(True)  # Right direction
            siblings.append(node.left_child)
            return True
            
        return False
    
    def verify_proof(self, proof: MerkleProof) -> bool:
        """
        Verify a Merkle proof against this tree's root.
        
        Args:
            proof: The MerkleProof to verify
            
        Returns:
            True if the proof is valid, False otherwise
        """
        if not self.root_hash:
            return False
            
        return proof.verify(self.root_hash)
    
    def create_resolver(self) -> MerkleResolver:
        """
        Create a resolver for this tree.
        
        Returns:
            A MerkleResolver for querying data
        """
        if not self.root_hash:
            raise ValueError("Cannot create resolver for empty tree")
            
        return MerkleResolver(self.storage, self.root_hash)
    
    @classmethod
    def load_from_storage(cls, storage, root_hash: bytes) -> 'MerkleTree':
        """
        Load a Merkle tree from storage using its root hash.
        
        Args:
            storage: The storage object to load from
            root_hash: The root hash of the tree to load
            
        Returns:
            A MerkleTree object initialized with the loaded tree
        """
        tree = cls(storage)
        tree.root_hash = root_hash
        
        # Cache the root node
        root_data = storage.get(root_hash)
        if root_data:
            root_node = MerkleNode.deserialize(root_data)
            tree.nodes[root_hash] = root_node
            
        return tree
    
    def get_root_hash(self) -> Optional[bytes]:
        """
        Get the root hash of this tree.
        
        Returns:
            The root hash, or None if the tree is empty
        """
        return self.root_hash
