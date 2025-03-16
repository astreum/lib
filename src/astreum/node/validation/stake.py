"""
Stake management for validators.
"""

import time
import random
import json
from typing import Dict, List, Optional, Tuple

from ...crypto import hash_data
from ..models import Transaction, TransactionType
from ..storage import Storage, MerkleNode
from .constants import SLOT_DURATION, MIN_STAKE_AMOUNT, VALIDATION_ADDRESS
from .account import Account


def get_validator_stake(storage: Storage, stake_root: bytes, validator_address: bytes) -> int:
    """
    Get the stake amount for a specific validator.
    
    Args:
        storage: Storage instance
        stake_root: Root hash of the stake Merkle tree
        validator_address: Address of the validator to check
        
    Returns:
        Stake amount for the validator, or 0 if not a validator
    """
    from ..storage.merkle import find_first
    
    # Find the validator node containing the stake information
    def match_validator(node_data: bytes) -> bool:
        try:
            stake_data = json.loads(node_data.decode('utf-8'))
            return stake_data.get('address') == validator_address.hex()
        except:
            return False
    
    validator_node = find_first(storage, stake_root, match_validator)
    
    if validator_node:
        try:
            stake_data = json.loads(validator_node.decode('utf-8'))
            return stake_data.get('stake', 0)
        except:
            return 0
    
    return 0


def is_validator(storage: Storage, stake_root: bytes, address: bytes) -> bool:
    """
    Check if an address is registered as a validator.
    
    Args:
        storage: Storage instance
        stake_root: Root hash of the stake Merkle tree
        address: Address to check
        
    Returns:
        True if the address is a validator, False otherwise
    """
    stake = get_validator_stake(storage, stake_root, address)
    return stake >= MIN_STAKE_AMOUNT


def get_all_validators(storage: Storage, stake_root: bytes) -> Dict[bytes, int]:
    """
    Get all validators and their stakes.
    
    Args:
        storage: Storage instance
        stake_root: Root hash of the stake Merkle tree
        
    Returns:
        Dictionary mapping validator addresses to their stakes
    """
    from ..storage.merkle import find_all
    
    validators = {}
    
    # Find all validator nodes containing stake information
    def match_all_validators(node_data: bytes) -> bool:
        return True  # Match all nodes
    
    validator_nodes = find_all(storage, stake_root, match_all_validators)
    
    for node_data in validator_nodes:
        try:
            stake_data = json.loads(node_data.decode('utf-8'))
            address = bytes.fromhex(stake_data.get('address', ''))
            stake = stake_data.get('stake', 0)
            
            if stake >= MIN_STAKE_AMOUNT:
                validators[address] = stake
        except:
            continue
    
    return validators


def process_stake_transaction(
    storage: Storage, 
    stake_root: bytes, 
    validator_address: bytes, 
    amount: int
) -> bytes:
    """
    Process a staking transaction and update the stake tree.
    
    Args:
        storage: Storage instance
        stake_root: Current root hash of the stake Merkle tree
        validator_address: Address of the validator staking tokens
        amount: Amount being staked
        
    Returns:
        New root hash of the stake Merkle tree after the update
    """
    from ..storage.merkle import find_first, MerkleTree
    
    # Find the validator node if it exists
    def match_validator(node_data: bytes) -> bool:
        try:
            stake_data = json.loads(node_data.decode('utf-8'))
            return stake_data.get('address') == validator_address.hex()
        except:
            return False
    
    validator_node = find_first(storage, stake_root, match_validator)
    
    # Create or update the validator stake
    if validator_node:
        # Update existing validator
        try:
            stake_data = json.loads(validator_node.decode('utf-8'))
            current_stake = stake_data.get('stake', 0)
            stake_data['stake'] = current_stake + amount
            updated_node = json.dumps(stake_data).encode('utf-8')
            
            # Replace the node in the tree
            merkle_tree = MerkleTree(storage)
            merkle_tree.root_hash = stake_root
            new_root = merkle_tree.add(updated_node)
        except Exception as e:
            print(f"Error updating validator stake: {e}")
            return stake_root
    else:
        # Create new validator
        stake_data = {
            'address': validator_address.hex(),
            'stake': amount,
            'last_update': int(time.time())
        }
        new_node = json.dumps(stake_data).encode('utf-8')
        
        # Add the node to the tree
        merkle_tree = MerkleTree(storage)
        if stake_root:
            merkle_tree.root_hash = stake_root
            new_root = merkle_tree.add(new_node)
        else:
            new_root = merkle_tree.add([new_node])
    
    return new_root


class SlotManager:
    """
    Manager for tracking slots and selecting validators.
    """
    
    def __init__(self, storage: Storage, stake_root: bytes = None):
        """
        Initialize slot manager.
        
        Args:
            storage: Storage instance
            stake_root: Root hash of the stake Merkle tree
        """
        self.storage = storage
        self.stake_root = stake_root
        
    def get_current_slot(self) -> int:
        """
        Get the current slot based on current time.
        
        Returns:
            Current slot number
        """
        return int(time.time() // SLOT_DURATION)
        
    def select_validator_for_slot(self, slot: int, previous_vdf: bytes) -> Optional[bytes]:
        """
        Select a validator for the given slot.
        
        Args:
            slot: Slot number
            previous_vdf: VDF output from previous block
            
        Returns:
            Selected validator address, or None if no validators available
        """
        # Get all validators
        validators = get_all_validators(self.storage, self.stake_root)
        
        if not validators:
            return None
            
        # Generate random seed based on slot and previous VDF
        seed = hash_data(previous_vdf + slot.to_bytes(8, byteorder='big'))
        
        # Select validator based on stake and random seed
        total_stake = sum(validators.values())
        if total_stake == 0:
            return None
            
        # Convert seed to a random number between 0 and 1
        random_value = int.from_bytes(seed, byteorder='big') / (2**(len(seed) * 8) - 1)
        
        # Select validator based on stake weight
        cumulative_prob = 0
        for validator, stake in validators.items():
            cumulative_prob += stake / total_stake
            if random_value <= cumulative_prob:
                return validator
                
        # Should never reach here unless there's a rounding error
        return list(validators.keys())[0]
