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
    Each k-bucket is a list of nodes with specific IDs in a certain distance range from ourselves.
    """
    
    def __init__(self, config: dict, our_node_id: bytes):
        """
        Initialize the routing table.
        
        Args:
            config (dict): Configuration dictionary
            our_node_id (bytes): Our node's unique identifier
        """
        self.our_node_id = our_node_id
        self.bucket_size = config.get('max_peers_per_bucket', 20)
        self.buckets: Dict[int, KBucket] = {}
        self.peer_manager = PeerManager(our_node_id)
        
    def add_peer(self, peer: Peer) -> bool:
        """
        Add a peer to the appropriate k-bucket based on distance.
        
        Args:
            peer (Peer): The peer to add
            
        Returns:
            bool: True if the peer was added, False otherwise
        """
        distance = self.peer_manager.calculate_distance(peer.public_key)
        
        # Create bucket if it doesn't exist
        if distance not in self.buckets:
            self.buckets[distance] = KBucket(self.bucket_size)
            
        # Add to bucket
        return self.buckets[distance].add(peer.address)
        
    def remove_peer(self, peer: Peer) -> bool:
        """
        Remove a peer from its k-bucket.
        
        Args:
            peer (Peer): The peer to remove
            
        Returns:
            bool: True if the peer was removed, False otherwise
        """
        distance = self.peer_manager.calculate_distance(peer.public_key)
        
        if distance in self.buckets:
            return self.buckets[distance].remove(peer.address)
        return False
            
    def get_closest_peers(self, target_id: bytes, limit: int = 20) -> List[Peer]:
        """
        Get the closest peers to a target ID.
        
        Args:
            target_id (bytes): The target ID to find closest peers to
            limit (int): Maximum number of peers to return
            
        Returns:
            List[Peer]: The closest peers
        """
        # Calculate distances from all known peers to the target
        peers_with_distance = []
        
        for bucket in self.buckets.values():
            for address in bucket.addresses:
                peer = self.peer_manager.get_peer_by_address(address)
                if peer:
                    # Calculate XOR distance between target and this peer
                    xor_distance = 0
                    for i in range(min(len(target_id), len(peer.public_key))):
                        xor_bit = target_id[i] ^ peer.public_key[i]
                        xor_distance = (xor_distance << 8) | xor_bit
                    
                    peers_with_distance.append((peer, xor_distance))
        
        # Sort by distance (closest first)
        peers_with_distance.sort(key=lambda x: x[1])
        
        # Return only the peers (without distances), up to the limit
        return [p[0] for p in peers_with_distance[:limit]]
    
    def get_bucket_stats(self) -> Dict[int, int]:
        """
        Get statistics about the buckets in the routing table.
        
        Returns:
            Dict[int, int]: Mapping of distance to number of peers in that bucket
        """
        return {distance: len(bucket) for distance, bucket in self.buckets.items()}
    
    def get_peers_in_bucket(self, distance: int) -> List[Peer]:
        """
        Get all peers in a specific bucket.
        
        Args:
            distance (int): Bucket distance
            
        Returns:
            List[Peer]: Peers in the bucket
        """
        if distance not in self.buckets:
            return []
            
        peers = []
        for address in self.buckets[distance].addresses:
            peer = self.peer_manager.get_peer_by_address(address)
            if peer:
                peers.append(peer)
                
        return peers
