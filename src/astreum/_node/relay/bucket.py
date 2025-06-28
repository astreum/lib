"""
K-bucket implementation for Kademlia-style routing in Astreum node.
"""

from typing import List, Set
from .peer import Peer

class KBucket:
    """
    A Kademlia k-bucket that stores peers.
    
    K-buckets are used to store contact information for nodes in the DHT.
    When a new node is added, it's placed at the tail of the list.
    If a node is already in the list, it is moved to the tail.
    This creates a least-recently seen eviction policy.
    """
    
    def __init__(self, k: int = 20):
        """
        Initialize a k-bucket with a fixed size.
        
        Args:
            k (int): Maximum number of peers in the bucket
        """
        self.k = k
        self.peers: List[Peer] = []
        self._peer_ids: Set[bytes] = set()  # Track peer IDs for quick lookup

    def add(self, peer: Peer) -> bool:
        """
        Add peer to bucket if not full or if peer exists.
        
        Args:
            peer (Peer): Peer to add to the bucket
            
        Returns:
            bool: True if added/exists, False if bucket full and peer not in bucket
        """
        # If peer already in bucket, move to end (most recently seen)
        if peer.public_key in self._peer_ids:
            # Find and remove the peer
            for i, existing_peer in enumerate(self.peers):
                if existing_peer.public_key == peer.public_key:
                    del self.peers[i]
                    break
            
            # Add back at the end (most recently seen)
            self.peers.append(peer)
            peer.update_last_seen()
            return True
            
        # If bucket not full, add peer
        if len(self.peers) < self.k:
            self.peers.append(peer)
            self._peer_ids.add(peer.public_key)
            peer.update_last_seen()
            return True
            
        # Bucket full and peer not in bucket
        return False

    def remove(self, peer: Peer) -> bool:
        """
        Remove peer from bucket.
        
        Args:
            peer (Peer): Peer to remove
            
        Returns:
            bool: True if removed, False if not in bucket
        """
        if peer.public_key in self._peer_ids:
            for i, existing_peer in enumerate(self.peers):
                if existing_peer.public_key == peer.public_key:
                    del self.peers[i]
                    self._peer_ids.remove(peer.public_key)
                    return True
        return False
        
    def get_peers(self) -> List[Peer]:
        """Get all peers in the bucket."""
        return self.peers.copy()
        
    def contains(self, peer_id: bytes) -> bool:
        """Check if a peer ID is in the bucket."""
        return peer_id in self._peer_ids
        
    def __len__(self) -> int:
        """Get the number of peers in the bucket."""
        return len(self.peers)
