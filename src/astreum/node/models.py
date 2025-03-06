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

class Node:
    def __init__(self, config: dict):
        self.config = config
        self.node_id = config.get('node_id', os.urandom(32))  # Default to random ID if not provided
        self.relay = Relay(config)
        self.storage = Storage(config)
        self.machine = AstreumMachine(config)
        self.route_table = RouteTable(config, self.node_id)
        
        # Register message handlers
        self._register_message_handlers()
        
    def _register_message_handlers(self):
        """Register handlers for different message topics."""
        self.relay.register_message_handler(Topic.PING, self._handle_ping)
        self.relay.register_message_handler(Topic.OBJECT_REQUEST, self._handle_object_request)
        self.relay.register_message_handler(Topic.ROUTE_REQUEST, self._handle_route_request)
        self.relay.register_message_handler(Topic.LATEST_BLOCK_REQUEST, self._handle_latest_block_request)
        
    def _handle_ping(self, body: bytes, addr: Tuple[str, int], envelope):
        """Handle ping messages by responding with a ping."""
        self.relay.send_message(b"pong", Topic.PING, addr)
    
    def _handle_object_request(self, body: bytes, addr: Tuple[str, int], envelope):
        """Handle request for an object by its hash."""
        # The body is the hash of the requested object
        object_hash = body
        object_data = self.storage.get(object_hash)
        
        if object_data:
            # Object found, send it back
            self.relay.send_message(object_data, Topic.OBJECT, addr)
        else:
            # Object not found, relay the request to peers
            closest_peers = self.route_table.get_closest_peers(object_hash, 3)
            
            # Forward request to closest peers who might have the object
            for peer in closest_peers:
                if peer.address != addr:  # Don't send back to the requester
                    self.relay.send_message(object_hash, Topic.OBJECT_REQUEST, peer.address)
    
    def _handle_route_request(self, body: bytes, addr: Tuple[str, int], envelope):
        """Handle request for routing information."""
        # The body contains the target node ID
        target_id = body
        
        # Get closest peers to the target
        closest_peers = self.route_table.get_closest_peers(target_id, 10)
        
        # Encode the peers information - in a real implementation, this would serialize the peer list
        peers_data = b""  # Placeholder
        
        # Send routing information back
        self.relay.send_message(peers_data, Topic.ROUTE, addr)
    
    def _handle_latest_block_request(self, body: bytes, addr: Tuple[str, int], envelope):
        """Handle request for the latest block."""
        # This would retrieve the latest block from blockchain
        # For now just sending a placeholder
        self.relay.send_message(b"latest_block_data", Topic.LATEST_BLOCK, addr)

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
