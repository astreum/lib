from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives import serialization
from datetime import datetime, timezone
from typing import Optional, Tuple

class Peer:
    shared_key: bytes
    timestamp: datetime
    latest_block: bytes
    address: Optional[Tuple[str, int]]
    public_key: X25519PublicKey
    public_key_bytes: bytes

    def __init__(self, my_sec_key: X25519PrivateKey, peer_pub_key: X25519PublicKey):
        self.shared_key = my_sec_key.exchange(peer_pub_key)
        self.timestamp = datetime.now(timezone.utc)
        self.latest_block = b""
        self.address = None
        self.public_key = peer_pub_key
        self.public_key_bytes = peer_pub_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
