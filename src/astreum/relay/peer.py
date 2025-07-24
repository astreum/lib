from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from datetime import datetime, timezone

class Peer:
    shared_key: bytes
    timestamp: datetime
    def __init__(self, my_sec_key: X25519PrivateKey, peer_pub_key: X25519PublicKey):
        self.shared_key = my_sec_key.exchange(peer_pub_key)
        self.timestamp = datetime.now(timezone.utc)