"""
K-bucket implementation for Kademlia-style routing in Astreum node.
"""

from typing import List, Tuple

class KBucket:
    """
    A Kademlia k-bucket that stores peers.
    
    K-buckets are used to store contact information for nodes in the DHT.
    When a new node is added, it's placed at the tail of the list.
    If a node is already in the list, it is moved to the tail.
    This creates a least-recently seen eviction policy.
    """
    
    def __init__(self, size: int):
        """
        Initialize a k-bucket with a fixed size.
        
        Args:
            size (int): Maximum number of peers in the bucket
        """
        self.size = size
        self.peers: List[Tuple[str, int]] = []

    def add(self, peer: Tuple[str, int]) -> bool:
        """
        Add peer to bucket if not full or if peer exists.
        
        Args:
            peer (Tuple[str, int]): Peer address (host, port)
            
        Returns:
            bool: True if added/exists, False if bucket full and peer not in bucket
        """
        if peer in self.peers:
            # Move to end (most recently seen)
            self.peers.remove(peer)
            self.peers.append(peer)
            return True
        
        if len(self.peers) < self.size:
            self.peers.append(peer)
            return True
            
        return False

    def remove(self, peer: Tuple[str, int]) -> bool:
        """
        Remove peer from bucket.
        
        Args:
            peer (Tuple[str, int]): Peer address to remove
            
        Returns:
            bool: True if peer was removed, False if peer not in bucket
        """
        if peer in self.peers:
            self.peers.remove(peer)
            return True
        return False
        
    def get_peers(self) -> List[Tuple[str, int]]:
        """
        Get all peers in the bucket.
        
        Returns:
            List[Tuple[str, int]]: List of peer addresses
        """
        return self.peers.copy()
        
    def __len__(self) -> int:
        """
        Get the number of peers in the bucket.
        
        Returns:
            int: Number of peers
        """
        return len(self.peers)
