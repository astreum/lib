"""
Utility functions for working with the storage module and Merkle trees,
with special focus on validator stake operations and binary searches.
"""

from typing import List, Dict, Optional, Tuple, Any, Callable, TypeVar
from .merkle import MerkleTree, MerkleProof, MerkleNode, MerkleNodeType
from .merkle import find_first, find_all, map, binary_search

T = TypeVar('T')


def create_ordered_merkle_tree(items: List[bytes], storage=None) -> Tuple[bytes, MerkleTree]:
    """
    Create a new ordered Merkle tree from items.
    
    Args:
        items: List of items to include in the tree, will be sorted
        storage: Optional storage backend to persist the tree
        
    Returns:
        Tuple of (root_hash, merkle_tree)
    """
    tree = MerkleTree(storage)
    root_hash = tree.add_sorted(items)
    return root_hash, tree


def query_validator_stake(storage, stake_root_hash: bytes, validator_address: bytes) -> Optional[int]:
    """
    Query a validator's stake by their address from a stake Merkle tree.
    
    Args:
        storage: Storage instance used by the Merkle tree
        stake_root_hash: Root hash of the stake Merkle tree
        validator_address: Address of the validator to look up
        
    Returns:
        The validator's stake amount as an integer, or None if not found
    """
    # Define a comparison function for binary search (assuming address is first part of data)
    def compare_address(data: bytes) -> int:
        # Extract address from data (format depends on how stakes are stored)
        # Assuming format: [address][stake]
        data_address = data[:len(validator_address)]
        
        if data_address < validator_address:
            return 1  # Data is less than target
        elif data_address > validator_address:
            return -1  # Data is greater than target
        else:
            return 0  # Match found
    
    # Binary search for the validator's stake
    stake_data = binary_search(storage, stake_root_hash, compare_address)
    
    if stake_data:
        # Extract stake amount from data
        # Assuming format: [address][stake_amount as 8-byte integer]
        address_len = len(validator_address)
        stake_amount = int.from_bytes(stake_data[address_len:address_len+8], byteorder='big')
        return stake_amount
    
    return None


def find_validator_stakes(storage, stake_root_hash: bytes, min_stake: int = 0) -> List[Tuple[bytes, int]]:
    """
    Find all validators with stakes above a minimum threshold.
    
    Args:
        storage: Storage instance used by the Merkle tree
        stake_root_hash: Root hash of the stake Merkle tree
        min_stake: Minimum stake threshold (default: 0)
        
    Returns:
        List of (validator_address, stake_amount) tuples
    """
    # Define predicate to filter validators by minimum stake
    def has_min_stake(data: bytes) -> bool:
        # Assuming format: [address][stake_amount as 8-byte integer]
        address_len = len(data) - 8  # Adjust based on your actual format
        stake_amount = int.from_bytes(data[address_len:], byteorder='big')
        return stake_amount >= min_stake
    
    # Define transform to extract address and stake
    def extract_address_and_stake(data: bytes) -> Tuple[bytes, int]:
        # Assuming format: [address][stake_amount as 8-byte integer]
        address_len = len(data) - 8  # Adjust based on your actual format
        address = data[:address_len]
        stake = int.from_bytes(data[address_len:], byteorder='big')
        return (address, stake)
    
    # Find all validators meeting criteria and transform results
    matching_validators = find_all(storage, stake_root_hash, has_min_stake)
    return [extract_address_and_stake(data) for data in matching_validators]


def get_total_stake(storage, stake_root_hash: bytes) -> int:
    """
    Calculate the total stake across all validators.
    
    Args:
        storage: Storage instance used by the Merkle tree
        stake_root_hash: Root hash of the stake Merkle tree
        
    Returns:
        Total stake amount
    """
    # Define transform to extract stake amount
    def extract_stake(data: bytes) -> int:
        # Assuming format: [address][stake_amount as 8-byte integer]
        address_len = len(data) - 8  # Adjust based on your actual format
        return int.from_bytes(data[address_len:], byteorder='big')
    
    # Map all leaves to their stake values and sum
    stakes = map(storage, stake_root_hash, extract_stake)
    return sum(stakes)


def query_with_custom_resolver(storage, root_hash: bytes, 
                              resolver_fn: Callable[[bytes], T]) -> T:
    """
    Query a Merkle tree using a custom resolver function.
    
    This is a general-purpose function that allows custom logic to be applied
    to tree traversal and data extraction.
    
    Args:
        storage: Storage instance used by the Merkle tree
        root_hash: Root hash of the Merkle tree
        resolver_fn: Function that takes a root hash and returns a result
        
    Returns:
        Whatever the resolver function returns
    """
    return resolver_fn(root_hash)
