"""
Peer management for Astreum node's Kademlia-style network.
"""

from dataclasses import dataclass
from typing import Tuple, Optional
import time

@dataclass
class Peer:
    """
    Represents a peer in the Astreum network.
    
    Attributes:
        address (Tuple[str, int]): The network address (host, port)
        public_key (bytes): The public key of the peer
        difficulty (int): The proof-of-work difficulty required for this peer
        last_seen (int): Timestamp when the peer was last seen
        failed_attempts (int): Number of consecutive failed communication attempts
    """
    address: Tuple[str, int]
    public_key: bytes
    difficulty: int = 1
    last_seen: int = 0
    failed_attempts: int = 0
    
    def __post_init__(self):
        if self.last_seen == 0:
            self.last_seen = int(time.time())
    
    def update_last_seen(self):
        """Update the last seen timestamp to current time."""
        self.last_seen = int(time.time())
        self.failed_attempts = 0
    
    def register_failed_attempt(self):
        """Register a failed communication attempt with this peer."""
        self.failed_attempts += 1
    
    def is_active(self, max_age: int = 3600, max_failures: int = 3) -> bool:
        """
        Check if the peer is considered active.
        
        Args:
            max_age (int): Maximum age in seconds before peer is considered inactive
            max_failures (int): Maximum consecutive failures before peer is considered inactive
            
        Returns:
            bool: True if the peer is active, False otherwise
        """
        current_time = int(time.time())
        return (
            (current_time - self.last_seen) <= max_age and 
            self.failed_attempts < max_failures
        )

class PeerManager:
    """
    Manages a collection of peers and provides utilities for peer operations.
    """
    
    def __init__(self, our_node_id: bytes):
        """
        Initialize a peer manager.
        
        Args:
            our_node_id (bytes): Our node's unique identifier
        """
        self.our_node_id = our_node_id
        self.peers_by_id = {}  # node_id: Peer
        self.peers_by_address = {}  # address: Peer
    
    def add_or_update_peer(self, address: Tuple[str, int], public_key: bytes) -> Peer:
        """
        Add a new peer or update an existing one.
        
        Args:
            address (Tuple[str, int]): Network address (host, port)
            public_key (bytes): The public key of the peer
            
        Returns:
            Peer: The added or updated peer
        """
        # Check if we already know this peer by ID
        if public_key in self.peers_by_id:
            peer = self.peers_by_id[public_key]
            # Update address if changed
            if peer.address != address:
                if peer.address in self.peers_by_address:
                    del self.peers_by_address[peer.address]
                peer.address = address
                self.peers_by_address[address] = peer
            peer.update_last_seen()
            return peer
        
        # Check if address exists with different ID
        if address in self.peers_by_address:
            old_peer = self.peers_by_address[address]
            if old_peer.public_key in self.peers_by_id:
                del self.peers_by_id[old_peer.public_key]
        
        # Create and add new peer
        peer = Peer(address=address, public_key=public_key)
        self.peers_by_id[public_key] = peer
        self.peers_by_address[address] = peer
        return peer
    
    def get_peer_by_id(self, public_key: bytes) -> Optional[Peer]:
        """
        Get a peer by its public key.
        
        Args:
            public_key (bytes): The peer's public key
            
        Returns:
            Optional[Peer]: The peer if found, None otherwise
        """
        return self.peers_by_id.get(public_key)
    
    def get_peer_by_address(self, address: Tuple[str, int]) -> Optional[Peer]:
        """
        Get a peer by its network address.
        
        Args:
            address (Tuple[str, int]): The peer's network address
            
        Returns:
            Optional[Peer]: The peer if found, None otherwise
        """
        return self.peers_by_address.get(address)
    
    def remove_peer(self, public_key: bytes) -> bool:
        """
        Remove a peer by its public key.
        
        Args:
            public_key (bytes): The peer's public key
            
        Returns:
            bool: True if the peer was removed, False otherwise
        """
        if public_key in self.peers_by_id:
            peer = self.peers_by_id[public_key]
            del self.peers_by_id[public_key]
            if peer.address in self.peers_by_address:
                del self.peers_by_address[peer.address]
            return True
        return False
    
    def calculate_distance(self, public_key: bytes) -> int:
        """
        Calculate the XOR distance between our node ID and the given public key.
        
        In Kademlia, peers are organized into buckets based on the XOR distance.
        The bucket index (0-255) represents the position of the first bit that differs.
        
        Args:
            public_key (bytes): The remote node's public key
            
        Returns:
            int: XOR distance (0-255)
        """
        # Assuming IDs are 256-bit (32 bytes)
        for i in range(min(len(self.our_node_id), len(public_key))):
            xor_byte = self.our_node_id[i] ^ public_key[i]
            if xor_byte == 0:
                continue
                
            # Find the most significant bit
            for bit in range(7, -1, -1):
                if (xor_byte >> bit) & 1:
                    return (i * 8) + (7 - bit)
        
        return 255  # Default maximum distance
