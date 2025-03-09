import socket
from pathlib import Path
from typing import Optional, Tuple, Dict
from astreum.machine import AstreumMachine
from .relay import Relay
from .relay.message import Topic
from .relay.route import RouteTable
from .relay.peer import Peer
import os
import struct
import threading
import time

class Storage:
    def __init__(self, config: dict):
        self.max_space = config.get('max_storage_space', 1024 * 1024 * 1024)  # Default 1GB
        self.current_space = 0
        self.storage_path = Path(config.get('storage_path', 'storage'))
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.max_object_recursion = config.get('max_object_recursion', 50)
        self.network_request_timeout = config.get('network_request_timeout', 5.0)  # Default 5 second timeout
        self.node = None  # Will be set by the Node after initialization
        
        # In-progress requests tracking
        self.pending_requests = {}  # hash -> (start_time, event)
        self.request_lock = threading.Lock()
        
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
        
        # If this was a pending request, mark it as complete
        with self.request_lock:
            if data_hash in self.pending_requests:
                _, event = self.pending_requests[data_hash]
                event.set()  # Signal that the data is now available
        
        return True

    def _local_get(self, data_hash: bytes) -> Optional[bytes]:
        """Get data from local storage only, no network requests."""
        file_path = self.storage_path / data_hash.hex()
        if file_path.exists():
            return file_path.read_bytes()
        return None

    def get(self, data_hash: bytes, timeout: Optional[float] = None) -> Optional[bytes]:
        """
        Retrieve data by its hash, with network fallback.
        
        This function will first check local storage. If not found and a node is attached,
        it will initiate a network request asynchronously.
        
        Args:
            data_hash: The hash of the data to retrieve
            timeout: Timeout in seconds to wait for network request, None for default
            
        Returns:
            The data bytes if found, None otherwise
        """
        if timeout is None:
            timeout = self.network_request_timeout
            
        # First check local storage
        local_data = self._local_get(data_hash)
        if local_data:
            return local_data
            
        # If no node is attached, we can't make network requests
        if self.node is None:
            return None
            
        # Check if there's already a pending request for this hash
        with self.request_lock:
            if data_hash in self.pending_requests:
                start_time, event = self.pending_requests[data_hash]
                # If this request has been going on too long, cancel it and start a new one
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    # Cancel the old request
                    self.pending_requests.pop(data_hash)
                else:
                    # Wait for the existing request to complete
                    wait_time = timeout - elapsed
            else:
                # No existing request, create a new one
                event = threading.Event()
                self.pending_requests[data_hash] = (time.time(), event)
                # Start the actual network request in a separate thread
                threading.Thread(
                    target=self._request_from_network,
                    args=(data_hash,),
                    daemon=True
                ).start()
                wait_time = timeout
                
        # Wait for the request to complete or timeout
        if event.wait(wait_time):
            # Event was set, data should be available now
            with self.request_lock:
                if data_hash in self.pending_requests:
                    self.pending_requests.pop(data_hash)
            
            # Check if data is now in local storage
            return self._local_get(data_hash)
        else:
            # Timed out waiting for data
            with self.request_lock:
                if data_hash in self.pending_requests:
                    self.pending_requests.pop(data_hash)
            return None
    
    def _request_from_network(self, data_hash: bytes):
        """
        Request object from the network.
        This is meant to be run in a separate thread.
        
        Args:
            data_hash: The hash of the object to request
        """
        try:
            if hasattr(self.node, 'request_object'):
                # Use the node's request_object method
                self.node.request_object(data_hash)
            # Note: We don't need to return anything or signal completion here
            # The put() method will signal completion when the object is received
        except Exception as e:
            print(f"Error requesting object {data_hash.hex()} from network: {e}")

    def contains(self, data_hash: bytes) -> bool:
        """Check if data exists in storage."""
        return (self.storage_path / data_hash.hex()).exists()
        
    def get_recursive(self, root_hash: bytes, max_depth: Optional[int] = None, 
                     timeout: Optional[float] = None) -> Dict[bytes, bytes]:
        """
        Recursively retrieve all objects starting from a root hash.
        
        Objects not found locally will be requested from the network.
        This method will continue processing objects that are available
        while waiting for network responses.
        
        Args:
            root_hash: The hash of the root object
            max_depth: Maximum recursion depth, defaults to self.max_object_recursion
            timeout: Time to wait for each object request, None for default
            
        Returns:
            Dictionary mapping object hashes to their data
        """
        if max_depth is None:
            max_depth = self.max_object_recursion
            
        if timeout is None:
            timeout = self.network_request_timeout
            
        # Start with the root object
        objects = {}
        pending_queue = [(root_hash, 0)]  # (hash, depth)
        processed = set()
        
        # Process objects in the queue
        while pending_queue:
            current_hash, current_depth = pending_queue.pop(0)
            
            # Skip if already processed or too deep
            if current_hash in processed or current_depth > max_depth:
                continue
                
            processed.add(current_hash)
            
            # Try to get the object (which may start a network request)
            obj_data = self.get(current_hash, timeout)
            if obj_data is None:
                # Failed to get this object, but we continue with the rest
                print(f"Warning: Failed to get object {current_hash.hex()}")
                continue
                
            # Store the object in our result
            objects[current_hash] = obj_data
            
            # Only process non-leaf nodes for recursion
            try:
                # Extract leaf flag and type
                is_leaf = struct.unpack("?", obj_data[0:1])[0]
                if is_leaf:
                    # Leaf node, no need to recurse
                    continue
                    
                type_indicator = obj_data[1:2]
                next_depth = current_depth + 1
                
                if type_indicator == b'L':  # List
                    # Non-leaf list has child element hashes
                    elements_bytes = obj_data[2:]
                    element_hashes = [elements_bytes[i:i+32] for i in range(0, len(elements_bytes), 32)]
                    
                    # Add each element hash to the queue
                    for elem_hash in element_hashes:
                        pending_queue.append((elem_hash, next_depth))
                        
                elif type_indicator == b'F':  # Function
                    # Non-leaf function has body hash
                    remaining_bytes = obj_data[2:]
                    
                    # Find the separator between params and body hash
                    params_end = remaining_bytes.find(b',', remaining_bytes.rfind(b','))
                    if params_end == -1:
                        params_end = 0  # No params
                        
                    body_hash = remaining_bytes[params_end+1:]
                    
                    # Add body hash to the queue
                    pending_queue.append((body_hash, next_depth))
                    
            except Exception as e:
                print(f"Error processing object {current_hash.hex()}: {e}")
                continue
                
        return objects

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
