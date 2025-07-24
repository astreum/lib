from typing import Dict, List
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey

class Route:
    def __init__(self, relay_public_key: X25519PublicKey, bucket_size: int = 16):
        self.relay_public_key_bytes = relay_public_key.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
        self.bucket_size = bucket_size
        self.buckets: Dict[int, List[X25519PublicKey]] = {
            i: [] for i in range(len(self.relay_public_key_bytes) * 8)
        }
        self.peers = {}

    @staticmethod
    def _matching_leading_bits(a: bytes, b: bytes) -> int:
        for byte_index, (ba, bb) in enumerate(zip(a, b)):
            diff = ba ^ bb
            if diff:
                return byte_index * 8 + (8 - diff.bit_length())
        return len(a) * 8

    def add_peer(self, peer_public_key: X25519PublicKey):
        peer_public_key_bytes = peer_public_key.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
        bucket_idx = self._matching_leading_bits(self.relay_public_key_bytes, peer_public_key_bytes)
        if len(self.buckets[bucket_idx]) < self.bucket_size:
            self.buckets[bucket_idx].append(peer_public_key)  
