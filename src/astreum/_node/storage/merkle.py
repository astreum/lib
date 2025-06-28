import blake3
from .storage import Storage
from astreum import format

class MerkleNode:
    def __init__(self, leaf: bool, data: bytes):
        """
        Initialize a Merkle node.
        
        For a leaf node, `data` is the actual content to be stored.
        For an internal node, `data` should be the concatenation of the two child hashes.
        
        :param leaf: A boolean flag indicating whether this node is a leaf node (True) or an internal node (False).
        :param data: The node's data. For leaves, the stored data; for internal nodes, concatenated child hashes.
        """
        self.leaf = leaf
        self.data = data
        self._hash = None  # Cached hash value to avoid recomputation.

    @classmethod
    def from_bytes(cls, data: bytes) -> 'MerkleNode':
        """
        Deserialize a MerkleNode from its byte representation.
        
        The input bytes are expected to be in the Astreum format, containing a leaf flag and node data.
        
        :param data: The serialized node data.
        :return: A new MerkleNode instance.
        """
        leaf_flag, node_data = format.decode(data)
        return cls(True if leaf_flag == 1 else False, node_data)

    @classmethod
    def from_storage(cls, storage: Storage, hash_value: bytes) -> 'MerkleNode' or None:
        """
        Retrieve and deserialize a MerkleNode from storage using its hash.
        
        :param storage: The Storage instance used to retrieve the node.
        :param hash_value: The hash key under which the node is stored.
        :return: A MerkleNode instance if found, otherwise None.
        """
        node_bytes = storage.get(hash_value)
        if node_bytes is None:
            return None
        return cls.from_bytes(node_bytes)

    def to_bytes(self) -> bytes:
        """
        Serialize the MerkleNode into bytes using the Astreum format.
        
        The format encodes a list containing the leaf flag and the node data.
        
        :return: The serialized bytes representing the node.
        """
        return format.encode([1 if self.leaf else 0, self.data])

    def hash(self) -> bytes:
        """
        Compute (or retrieve a cached) hash of the node using the Blake3 algorithm.
        
        For leaf nodes, the hash is computed over the actual data.
        For internal nodes, the hash is computed over the concatenated child hashes.
        
        :return: The Blake3 digest of the node's data.
        """
        if self._hash is None:
            self._hash = blake3.blake3(self.data).digest()
        return self._hash


class MerkleTree:
    def __init__(self, storage: Storage, root_hash: bytes = None, leaves: list[bytes] = None):
        """
        Initialize a Merkle tree from an existing root hash or by constructing a new tree from leaf data.
        
        If a list of leaf data is provided, the tree will be built from the bottom up,
        every node will be stored in the provided storage, and the computed root hash
        will be used as the tree's identifier.
        
        :param storage: A Storage instance used for storing and retrieving tree nodes.
        :param root_hash: An optional existing root hash of a Merkle tree.
        :param leaves: An optional list of leaf data (each as bytes). If provided, a new tree is built.
        :raises ValueError: If neither root_hash nor leaves is provided.
        """
        self.storage = storage
        if leaves is not None:
            self.root_hash = self.build_tree_from_leaves(leaves)
        elif root_hash is not None:
            self.root_hash = root_hash
        else:
            raise ValueError("Either root_hash or leaves must be provided.")

    def build_tree_from_leaves(self, leaves: list[bytes]) -> bytes:
        """
        Construct a Merkle tree from a list of leaf data and store each node in storage.
        
        Each leaf data entry is wrapped in a MerkleNode (with leaf=True) and stored.
        Then, nodes are paired (duplicating the last node if needed when the count is odd)
        to form parent nodes. For each parent node, the data is the concatenation of its
        two child hashes. This process repeats until a single root hash remains.
        
        :param leaves: A list of bytes objects, each representing leaf data.
        :return: The computed root hash of the newly built tree.
        """
        # Create leaf nodes and store them.
        current_level = []
        for leaf_data in leaves:
            leaf_node = MerkleNode(True, leaf_data)
            leaf_hash = leaf_node.hash()
            self.storage.put(leaf_hash, leaf_node.to_bytes())
            current_level.append(leaf_hash)

        # Build the tree upward until one node remains.
        while len(current_level) > 1:
            next_level = []
            # If an odd number of nodes, duplicate the last node.
            if len(current_level) % 2 == 1:
                current_level.append(current_level[-1])
            for i in range(0, len(current_level), 2):
                left_hash = current_level[i]
                right_hash = current_level[i + 1]
                # Create a parent node from the concatenated child hashes.
                parent_node = MerkleNode(False, left_hash + right_hash)
                parent_hash = parent_node.hash()
                self.storage.put(parent_hash, parent_node.to_bytes())
                next_level.append(parent_hash)
            current_level = next_level

        # The remaining hash is the root of the tree.
        return current_level[0]

    def get(self, index: int, level: int = 0) -> bytes:
        """
        Retrieve the data stored in the leaf at a given index.
        
        The method traverses the tree from the root, using the binary representation
        of the index to choose which branch to follow at each level. It assumes that
        non-leaf nodes store two child hashes concatenated together (each 32 bytes).
        
        :param index: The index of the leaf to retrieve. The bits of this number determine the path.
        :param level: The current tree level (used internally for recursion).
        :return: The data stored in the target leaf node, or None if not found.
        """
        current_node = MerkleNode.from_storage(self.storage, self.root_hash)
        if current_node is None:
            return None

        # If at a leaf node, return its data.
        if current_node.leaf:
            return current_node.data

        # For non-leaf nodes, extract the left and right child hashes.
        left_hash = current_node.data[:32]
        right_hash = current_node.data[32:64]

        # Use the bit at position `level` in the index to select the branch:
        # 0 selects the left branch, 1 selects the right branch.
        bit = (index >> level) & 1
        next_hash = left_hash if bit == 0 else right_hash

        # Recursively traverse the tree.
        return MerkleTree(self.storage, root_hash=next_hash).get(index, level + 1)

    def set(self, index: int, new_data: bytes) -> None:
        """
        Update the leaf at the specified index with new data, rebuilding all affected nodes.
        
        The update process recursively creates new nodes for the branch from the updated leaf
        back to the root. At each step, the old node is removed from storage and replaced with
        a new node that reflects the updated hash.
        
        :param index: The index of the leaf node to update.
        :param new_data: The new data (as bytes) to store in the leaf.
        """
        self.root_hash = self._update(self.root_hash, index, 0, new_data)

    def _update(self, node_hash: bytes, index: int, level: int, new_data: bytes) -> bytes:
        """
        Recursive helper function to update a node on the path to the target leaf.
        
        For a leaf node, a new node is created with the updated data.
        For an internal node, the correct branch (determined by the index and level) is updated,
        and a new parent node is constructed from the updated child hash and the unchanged sibling hash.
        
        :param node_hash: The hash of the current node to update.
        :param index: The target leaf index whose path is being updated.
        :param level: The current depth in the tree.
        :param new_data: The new data to set at the target leaf.
        :return: The hash of the newly constructed node replacing the current node.
        :raises Exception: If the node is not found in storage.
        """
        current_node = MerkleNode.from_storage(self.storage, node_hash)
        if current_node is None:
            raise Exception("Node not found in storage")

        if current_node.leaf:
            # At the leaf, create a new node with updated data.
            new_leaf = MerkleNode(True, new_data)
            new_hash = new_leaf.hash()
            self.storage.put(new_hash, new_leaf.to_bytes())
            self.storage.delete(node_hash)  # Remove the outdated node.
            return new_hash
        else:
            # For non-leaf nodes, update the correct branch.
            left_hash = current_node.data[:32]
            right_hash = current_node.data[32:64]
            bit = (index >> level) & 1

            if bit == 0:
                new_left_hash = self._update(left_hash, index, level + 1, new_data)
                new_right_hash = right_hash
            else:
                new_left_hash = left_hash
                new_right_hash = self._update(right_hash, index, level + 1, new_data)

            # Create a new parent node with updated child hashes.
            updated_node_data = new_left_hash + new_right_hash
            new_node = MerkleNode(False, updated_node_data)
            new_node_hash = new_node.hash()
            self.storage.put(new_node_hash, new_node.to_bytes())
            self.storage.delete(node_hash)  # Remove the outdated parent node.
            return new_node_hash


