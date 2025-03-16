"""
Blockchain state management.

This module manages the blockchain state, including accounts, blocks, and
transactions.
"""

import time
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from ..utils import hash_data
from ..models import Block, Transaction, Account as ModelAccount
from .account import Account
from .constants import VALIDATION_ADDRESS, BURN_ADDRESS, MIN_STAKE_AMOUNT


class BlockchainState:
    """
    Manages the state of the blockchain.
    
    This class tracks the current state of accounts, blocks, and transactions,
    and provides methods to update the state with new blocks and transactions.
    """
    
    def __init__(self, config: Optional[dict] = None):
        """
        Initialize blockchain state.
        
        Args:
            config: Optional configuration
        """
        self.config = config or {}
        
        # Dictionaries to track blockchain state
        self.accounts = {}  # address -> Account
        self.blocks = {}  # hash -> Block
        self.transactions = {}  # hash -> Transaction
        
        # Track the latest block
        self.latest_block = None
        
        # Pending transactions
        self.pending_transactions = set()  # Set of transaction hashes
        
        # State of validators and stakes
        self.validators = {}  # address -> stake amount
        
        # Initialize the genesis block if not provided
        if not self.latest_block:
            self._initialize_genesis()
    
    def _initialize_genesis(self):
        """Initialize the genesis block and state."""
        # In a full implementation, this would initialize the genesis
        # block and state from configuration
        print("Initializing genesis block and state")
    
    def add_block(self, block: Block) -> bool:
        """
        Add a block to the blockchain state.
        
        Args:
            block: Block to add
            
        Returns:
            True if block was added successfully, False otherwise
        """
        # Convert block to validation format directly
        validation_block = {
            'number': block.number,
            'timestamp': block.time,
            'producer': block.validator.public_key if block.validator else b'',
            'previous': block.previous.get_hash() if block.previous else b'',
            'transactions': self._extract_transactions(block),
            'vdf_proof': block.signature[:8],  # Use part of signature as VDF proof for demo
            'signature': block.signature
        }
        
        # Check for duplicate (already processed) blocks
        block_hash = block.get_hash()
        if block_hash in self.blocks:
            print(f"Block {block_hash.hex()} already in blockchain")
            return True
        
        # Convert block's accounts to validation accounts
        account_dict = {}
        # Here we would deserialize the accounts data from the block
        # In a real implementation, this would reconstruct accounts from serialized data
        
        # For now, we'll just log that we would process the block
        print(f"Processing block at height {block.number}")
        
        # Add the block to our state
        self.blocks[block_hash] = block
        
        # Update latest block if this is a new latest block
        if not self.latest_block or block.number > self.latest_block.number:
            self.latest_block = block
        
        # Process transactions in the block
        # This would update account states, apply transaction effects, etc.
        
        return True
    
    def _extract_transactions(self, block: Block) -> List[dict]:
        """
        Extract transactions from a block.
        
        Args:
            block: The model Block instance
            
        Returns:
            List of transactions in validation format
        """
        transactions = []
        # Parse transaction data from the block
        # In a real implementation, this would deserialize the transactions field
        # For now, we'll return an empty list as a placeholder
        return transactions
    
    def add_transaction(self, transaction: Transaction) -> bool:
        """
        Add a transaction to the pending set.
        
        Args:
            transaction: Transaction to add
            
        Returns:
            True if transaction was added successfully, False otherwise
        """
        # Convert transaction to validation format directly
        validation_tx = {
            'sender': transaction.sender.public_key if transaction.sender else b'',
            'recipient': transaction.receipient.public_key if transaction.receipient else b'',
            'amount': transaction.amount,
            'counter': transaction.counter,
            'data': transaction.data,
            'signature': transaction.signature
        }
        
        # Generate a transaction hash
        tx_hash = hash_data(str(validation_tx).encode())
        
        # Check for duplicate transactions
        if tx_hash in self.transactions or tx_hash in self.pending_transactions:
            print(f"Transaction {tx_hash.hex()} already processed or pending")
            return False
        
        # Validate the transaction
        # In a real implementation, this would check signature, sender balance, etc.
        
        # Add to pending transactions
        self.pending_transactions.add(tx_hash)
        
        return True
    
    def is_staking_transaction(self, tx: Transaction) -> bool:
        """
        Check if a transaction is a staking transaction.
        
        Args:
            tx: The model Transaction instance
            
        Returns:
            True if this is a staking transaction, False otherwise
        """
        # A transaction is a staking transaction if it's sending to the validation address
        if tx.receipient and hasattr(tx.receipient, 'public_key'):
            return tx.receipient.public_key == VALIDATION_ADDRESS
        return False
    
    def get_account(self, address: bytes) -> Optional[Account]:
        """
        Get an account by address.
        
        Args:
            address: Account address
            
        Returns:
            Account if found, None otherwise
        """
        return self.accounts.get(address)
    
    def get_validator_stake(self, address: bytes) -> int:
        """
        Get the stake of a validator.
        
        Args:
            address: Validator address
            
        Returns:
            Stake amount (0 if not a validator)
        """
        return self.validators.get(address, 0)
    
    def is_validator(self, address: bytes) -> bool:
        """
        Check if an address is a validator.
        
        Args:
            address: Address to check
            
        Returns:
            True if address is a validator, False otherwise
        """
        return self.get_validator_stake(address) >= MIN_STAKE_AMOUNT
    
    def get_pending_transactions(self) -> List[Transaction]:
        """
        Get all pending transactions.
        
        Returns:
            List of pending transactions
        """
        # In a real implementation, this would return the actual transaction objects
        # For now, we'll just return an empty list
        return []


def create_blockchain(config: Optional[dict] = None) -> BlockchainState:
    """
    Create a new blockchain state.
    
    Args:
        config: Optional configuration
        
    Returns:
        New BlockchainState instance
    """
    return BlockchainState(config)
