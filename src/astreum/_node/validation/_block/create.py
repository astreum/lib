"""
Block creation functionality for the Astreum blockchain.
"""

import time
from typing import Dict, List, Optional, Tuple, Set

from .model import Block
from ..account import Account
from ...models import Transaction
from ...utils import hash_data

def create_block(
    number: int,
    validator: bytes,
    previous: bytes,
    transactions: List[Transaction],
    timestamp: Optional[int] = None,
    vdf: Optional[bytes] = None,
    signature: Optional[bytes] = None,
    proof: Optional[bytes] = None,
    receipts: Optional[List] = None,
    data: Optional[bytes] = None,
    delay: Optional[int] = None,
    difficulty: Optional[int] = None,
    accounts: Optional[Dict] = None,
    chain: Optional[bytes] = None
) -> Block:
    """
    Create a new block.
    
    Args:
        number: Block number
        validator: Address of block validator
        previous: Hash of previous block
        transactions: List of transactions to include
        timestamp: Block timestamp (defaults to current time)
        vdf: VDF proof
        signature: Block signature
        proof: Additional proof data
        receipts: Transaction receipts
        data: Additional block data
        delay: Block delay
        difficulty: Block difficulty
        accounts: Accounts state
        chain: Chain identifier
        
    Returns:
        New Block object
    """
    # Use current time if timestamp not provided
    if timestamp is None:
        timestamp = int(time.time())
    
    # Create and return a new Block object
    return Block(
        number=number,
        validator=validator,
        previous=previous,
        transactions=transactions,
        timestamp=timestamp,
        vdf=vdf,
        signature=signature,
        proof=proof,
        receipts=receipts,
        data=data,
        delay=delay,
        difficulty=difficulty,
        accounts=accounts,
        chain=chain
    )

def create_genesis_block(validator_address: bytes) -> Block:
    """
    Create the genesis block.
    
    Args:
        validator_address: Address of the genesis block validator
        
    Returns:
        Genesis Block object
    """
    return create_block(
        number=0,
        validator=validator_address,
        previous=None,
        transactions=[],
        timestamp=int(time.time()),
        vdf=None,
        signature=None,
        proof=None,
        receipts=[],
        data=None,
        delay=0,
        difficulty=1,
        accounts={},
        chain=hash_data(b"genesis")
    )