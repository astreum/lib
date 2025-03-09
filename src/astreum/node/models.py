import socket
from pathlib import Path
from typing import Optional, Tuple
from astreum.machine import AstreumMachine
from .relay import Relay
from .relay.message import Topic
from .relay.route import RouteTable
from .relay.peer import Peer
import os

class Storage:
    def __init__(self, config: dict):
        self.max_space = config.get('max_storage_space', 1024 * 1024 * 1024)  # Default 1GB
        self.current_space = 0
        self.storage_path = Path(config.get('storage_path', 'storage'))
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Calculate current space usage
        self.current_space = sum(f.stat().st_size for f in self.storage_path.glob('*') if f.is_file())

    def put(self, data_hash: bytes, data: bytes) -> bool:
        """Store data with its hash. Returns True if successful, False if space limit exceeded."""
        data_size = len(data)
        if self.current_space + data_size > self.max_space:
            return False

        file_path = self.storage_path / data_hash.hex()
        
        # Don't store if already exists
        if file_path.exists():
            return True

        # Store the data
        file_path.write_bytes(data)
        self.current_space += data_size
        return True

    def get(self, data_hash: bytes) -> Optional[bytes]:
        """Retrieve data by its hash. Returns None if not found."""
        file_path = self.storage_path / data_hash.hex()
        if not file_path.exists():
            return None
        return file_path.read_bytes()

    def contains(self, data_hash: bytes) -> bool:
        """Check if data exists in storage."""
        return (self.storage_path / data_hash.hex()).exists()

class Account:
    def __init__(self, public_key: bytes, balance: int, counter: int):
        self.public_key = public_key
        self.balance = balance
        self.counter = counter

class Block:
    def __init__(
        self,
        accounts: bytes,
        chain: Chain,
        difficulty: int,
        delay: int,
        number: int,
        previous: Block,
        receipts: bytes,
        aster: int,
        time: int,
        transactions: bytes,
        validator: Account,
        signature: bytes
    ):
        self.accounts = accounts
        self.chain = chain
        self.difficulty = difficulty
        self.delay = delay
        self.number = number
        self.previous = previous
        self.receipts = receipts
        self.aster = aster
        self.time = time
        self.transactions = transactions
        self.validator = validator
        self.signature = signature

class Chain:
    def __init__(self, latest_block: Block):
        self.latest_block = latest_block
        
class Transaction:
    def __init__(self, chain: Chain, receipient: Account, sender: Account, counter: int, amount: int, signature: bytes, data: bytes):
        self.chain = chain
        self.receipient = receipient
        self.sender = sender
        self.counter = counter
        self.amount = amount
        self.signature = signature
        self.data = data
