from typing import Dict, List, Union
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

PeerKey = Union[X25519PublicKey, bytes, bytearray]


class Route:
    def __init__(self, relay_public_key: X25519PublicKey, bucket_size: int = 16):
        self.relay_public_key_bytes = relay_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.bucket_size = bucket_size
        self.buckets: Dict[int, List[bytes]] = {
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

    def _normalize_peer_key(self, peer_public_key: PeerKey) -> bytes:
        if isinstance(peer_public_key, X25519PublicKey):
            return peer_public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        if isinstance(peer_public_key, (bytes, bytearray)):
            key_bytes = bytes(peer_public_key)
            if len(key_bytes) != len(self.relay_public_key_bytes):
                raise ValueError("peer key must be raw 32-byte public key")
            return key_bytes
        raise TypeError("peer_public_key must be raw bytes or X25519PublicKey")

    def add_peer(self, peer_public_key: PeerKey):
        peer_public_key_bytes = self._normalize_peer_key(peer_public_key)
        bucket_idx = self._matching_leading_bits(self.relay_public_key_bytes, peer_public_key_bytes)
        if len(self.buckets[bucket_idx]) < self.bucket_size:
            bucket = self.buckets[bucket_idx]
            if peer_public_key_bytes not in bucket:
                bucket.append(peer_public_key_bytes)

    def remove_peer(self, peer_public_key: PeerKey):
        peer_public_key_bytes = self._normalize_peer_key(peer_public_key)
        bucket_idx = self._matching_leading_bits(self.relay_public_key_bytes, peer_public_key_bytes)
        bucket = self.buckets.get(bucket_idx)
        if not bucket:
            return
        try:
            bucket.remove(peer_public_key_bytes)
        except ValueError:
            pass
