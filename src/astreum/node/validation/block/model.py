"""
Block model for the Astreum blockchain.
"""

import time
import threading
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field

from ...node.storage.merkle import MerkleTree
from ...utils import hash_data

class Block:
    def __init__(self, number, validator, previous, transactions, timestamp, vdf, signature, proof, receipts, data, delay, difficulty, accounts=None, chain=None):
        self.accounts = accounts
        self.chain = chain
        self.data = data
        self.delay = delay
        self.difficulty = difficulty
        self.number = number
        self.validator = validator
        self.vdf = vdf
        self.previous = previous
        self.transactions = transactions
        self.timestamp = timestamp
        self.signature = signature
        self.proof = proof
        self.receipts = receipts

    def get_details_hash(self):
        detail_fields = [
            'accounts',
            'chain',
            'data',
            'delay',
            'difficulty',
            'number',
            'previous',
            'proof',
            'receipts',
            'timestamp',
            'transactions',
            'validator',
            'vdf',
        ]

        # Prepare serialized entries in the exact order of detail_fields
        serialized_entries = []
        for field in detail_fields:
            value = getattr(self, field, None)  # Use None if attribute doesn't exist
            
            # Convert value to bytes directly based on type
            if isinstance(value, (bytes, bytearray)):
                # Already bytes, use as is
                entry = value
            elif isinstance(value, (int, float)):
                # Convert numbers to bytes
                entry = str(value).encode('utf-8')
            elif isinstance(value, str):
                # Convert strings to bytes
                entry = value.encode('utf-8')
            elif value is None:
                # Handle None values
                entry = b''
            else:
                # For complex types, use their string representation
                entry = str(value).encode('utf-8')
                
            serialized_entries.append(entry)
        
        # Use MerkleTree from storage module
        merkle_tree = MerkleTree()
        merkle_tree.add(serialized_entries)
        
        return merkle_tree.get_root_hash()


    def get_hash(self):
        merkle_tree = MerkleTree()
        merkle_tree.add([self.get_details_hash(), self.signature])
        return merkle_tree.get_root_hash()