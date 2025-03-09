"""
Kademlia-style routing table implementation for Astreum node.
"""

from typing import List, Dict, Set, Tuple, Optional
from .bucket import KBucket
from .peer import Peer, PeerManager

class RouteTable:
    """
    Kademlia-style routing table using k-buckets.
    
    The routing table consists of k-buckets, each covering a specific range of distances.
    In Kademlia, bucket index (i) contains nodes that share exactly i bits with the local node:
    - Bucket 0: Contains peers that don't share the first bit with our node ID
    - Bucket 1: Contains peers that share the first bit, but differ on the second bit
    - Bucket 2: Contains peers that share the first two bits, but differ on the third bit
    - And so on...
    
    This structuring ensures efficient routing to any node in the network.
    """
    
    def __init__(self, relay):
        """
        Initialize the routing table.
        
        Args:
            relay: The relay instance this route table belongs to
        """
        self.relay = relay
        self.our_node_id = relay.node_id
        self.bucket_size = relay.config.get('max_peers_per_bucket', 20)
        # Initialize buckets - for a 256-bit key, we need up to 256 buckets
        self.buckets = {i: KBucket(k=self.bucket_size) for i in range(256)}
        self.peer_manager = PeerManager(self.our_node_id)
        
    def add_peer(self, peer: Peer) -> bool:
        """
        Add a peer to the appropriate k-bucket based on bit prefix matching.
        
        Args:
            peer (Peer): The peer to add
            
        Returns:
            bool: True if the peer was added, False otherwise
        """
        # Calculate the number of matching prefix bits
        matching_bits = self.peer_manager.calculate_distance(peer.public_key)
        
        # Add to the appropriate bucket based on the number of matching bits
        return self.buckets[matching_bits].add(peer)
        
    def update_peer(self, addr: tuple, public_key: bytes, difficulty: int = 1) -> Peer:
        """
        Update or add a peer to the routing table.
        
        Args:
            addr: Tuple of (ip, port)
            public_key: Peer's public key
            difficulty: Peer's proof-of-work difficulty
            
        Returns:
            Peer: The updated or added peer
        """
        # Create or update the peer
        peer = self.peer_manager.add_or_update_peer(addr, public_key)
        peer.difficulty = difficulty
        
        # Add to the appropriate bucket
        self.add_peer(peer)
        
        return peer
        
    def remove_peer(self, peer: Peer) -> bool:
        """
        Remove a peer from its k-bucket.
        
        Args:
            peer (Peer): The peer to remove
            
        Returns:
            bool: True if the peer was removed, False otherwise
        """
        matching_bits = self.peer_manager.calculate_distance(peer.public_key)
        if matching_bits in self.buckets:
            return self.buckets[matching_bits].remove(peer)
        return False
        
    def get_closest_peers(self, target_id: bytes, count: int = 3) -> List[Peer]:
        """
        Get the closest peers to the target ID.
        
        Args:
            target_id: Target ID to find peers close to
            count: Maximum number of peers to return
            
        Returns:
            List of peers closest to the target ID
        """
        # Calculate the number of matching prefix bits with the target
        matching_bits = self.peer_manager.calculate_distance(target_id)
        
        closest_peers = []
        
        # First check the exact matching bucket
        if matching_bits in self.buckets:
            bucket_peers = self.buckets[matching_bits].get_peers()
            closest_peers.extend(bucket_peers)
            
        # If we need more peers, also check adjacent buckets (farther first)
        if len(closest_peers) < count:
            # Check buckets with fewer matching bits (higher XOR distance)
            for i in range(matching_bits - 1, -1, -1):
                if i in self.buckets:
                    bucket_peers = self.buckets[i].get_peers()
                    closest_peers.extend(bucket_peers)
                    if len(closest_peers) >= count:
                        break
                        
            # If still not enough, check buckets with more matching bits
            if len(closest_peers) < count:
                for i in range(matching_bits + 1, 256):
                    if i in self.buckets:
                        bucket_peers = self.buckets[i].get_peers()
                        closest_peers.extend(bucket_peers)
                        if len(closest_peers) >= count:
                            break
        
        # Return the closest peers, limited by count
        return closest_peers[:count]
    
    def get_bucket_peers(self, bucket_index: int) -> List[Peer]:
        """
        Get all peers from a specific bucket.
        
        Args:
            bucket_index: Index of the bucket to get peers from
            
        Returns:
            List of peers in the bucket
        """
        if bucket_index in self.buckets:
            return self.buckets[bucket_index].get_peers()
        return []
        
    def has_peer(self, addr: tuple) -> bool:
        """
        Check if a peer with the given address exists in the routing table.
        
        Args:
            addr: Tuple of (ip, port)
            
        Returns:
            bool: True if the peer exists, False otherwise
        """
        return self.peer_manager.get_peer_by_address(addr) is not None
    
    @property
    def num_buckets(self) -> int:
        """Get the number of active buckets."""
        return len(self.buckets)
