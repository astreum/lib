from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives import serialization
from datetime import datetime, timezone
from typing import Optional, Tuple

class Peer:
    def __init__(
        self,
        node_secret_key: X25519PrivateKey,
        peer_public_key: X25519PublicKey,
        latest_block: Optional[bytes] = None,
        address: Optional[Tuple[str, int]] = None,
    ):
        self.shared_key_bytes = node_secret_key.exchange(peer_public_key)
        self.timestamp = datetime.now(timezone.utc)
        self.latest_block = latest_block
        self.address = address
        self.public_key_bytes = peer_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
