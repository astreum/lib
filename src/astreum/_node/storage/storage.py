"""
Storage implementation for the Astreum node.

This module provides a Storage class that manages persistent storage
of data using either in-memory dictionaries or file system storage.
It supports network-based retrieval for missing data.
"""

import threading
import time
from pathlib import Path
from typing import Optional, Dict, Set, Tuple, List, Any


class Storage:
    def __init__(self, config: dict):
        self.max_space = config.get('max_storage_space', 1024 * 1024 * 1024)  # Default 1GB
        self.current_space = 0
        
        # Check if storage_path is provided in config
        storage_path = config.get('storage_path')
        self.use_memory_storage = storage_path is None
        
        # Initialize in-memory storage if no path provided
        self.memory_storage = {} if self.use_memory_storage else None
        
        # Only create storage path if not using memory storage
        if not self.use_memory_storage:
            self.storage_path = Path(storage_path)
            self.storage_path.mkdir(parents=True, exist_ok=True)
            # Calculate current space usage
            self.current_space = sum(f.stat().st_size for f in self.storage_path.glob('*') if f.is_file())
        
        self.max_object_recursion = config.get('max_object_recursion', 50)
        self.network_request_timeout = config.get('network_request_timeout', 5.0)  # Default 5 second timeout
        self.node = None  # Will be set by the Node after initialization
        
        # In-progress requests tracking
        self.pending_requests = {}  # hash -> (start_time, event)
        self.request_lock = threading.Lock()

        

    def put(self, data_hash: bytes, data: bytes) -> bool:
        """Store data with its hash. Returns True if successful, False if space limit exceeded."""
        data_size = len(data)
        if self.current_space + data_size > self.max_space:
            return False

        # If using memory storage, store in dictionary
        if self.use_memory_storage:
            if data_hash not in self.memory_storage:
                self.memory_storage[data_hash] = data
                self.current_space += data_size
            return True

        # Otherwise use file storage
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
        # If using memory storage, get from dictionary
        if self.use_memory_storage:
            return self.memory_storage.get(data_hash)
            
        # Otherwise use file storage
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
        if self.use_memory_storage:
            return data_hash in self.memory_storage
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
                # Object not found, continue with other objects
                continue
                
            # Store the object
            objects[current_hash] = obj_data
            
            # Queue child objects if not at max depth
            if current_depth < max_depth:
                # Try to detect child objects in the data
                # This depends on the data format, so this is just a placeholder
                # In a real implementation, you would parse the data based on its format
                # and extract references to other objects
                child_hashes = self._extract_child_hashes(obj_data)
                for child_hash in child_hashes:
                    pending_queue.append((child_hash, current_depth + 1))
        
        return objects
    
    def _extract_child_hashes(self, data: bytes) -> List[bytes]:
        """
        Extract child object hashes from object data.
        This is a placeholder method that should be overridden or adapted based on the object format.
        
        Args:
            data: The object data
            
        Returns:
            List of child object hashes
        """
        # In a real implementation, this would parse the data based on its format
        # and extract references to other objects
        # For example, if the data is a serialized Merkle node, you might extract
        # left and right child hashes
        
        # For now, return an empty list
        return []
