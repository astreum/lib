import threading
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives import serialization
from datetime import datetime, timezone
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ...node import Node

class Peer:
    def __init__(
        self,
        node_secret_key: X25519PrivateKey,
        peer_public_key: X25519PublicKey,
        latest_block: Optional[bytes] = None,
        address: Optional[Tuple[str, int]] = None,
        is_default_seed: bool = False,
        difficulty: int = 1,
    ):
        self.shared_key_bytes = node_secret_key.exchange(peer_public_key)
        self.timestamp = datetime.now(timezone.utc)
        self.latest_block = latest_block
        self.difficulty = max(1, int(difficulty or 1))
        self.address = address
        self.is_default_seed = bool(is_default_seed)
        self.public_key_bytes = peer_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        # Traffic-sharing counters are updated by multiple communication threads.
        self.metrics_lock = threading.RLock()
        self.total_network_upload = 0
        self.total_network_download = 0
        self.shared_storage_upload = 0
        self.shared_storage_download = 0


def increment_peer_metric(peer: "Peer", attr_name: str, amount: int) -> None:
    """Increment a peer metric counter under the peer metrics lock."""
    try:
        delta = int(amount)
    except Exception:
        return
    if delta <= 0:
        return

    lock = getattr(peer, "metrics_lock", None)
    if lock is None:
        current = int(getattr(peer, attr_name, 0))
        setattr(peer, attr_name, current + delta)
        return

    with lock:
        current = int(getattr(peer, attr_name, 0))
        setattr(peer, attr_name, current + delta)


def add_peer(node: "Node", peer_key, peer: "Peer") -> "Peer":
    """Register a peer entry on the node under lock."""
    with node.peers_lock:
        node.peers[peer_key] = peer
    return peer


def replace_peer(node: "Node", old_key, peer_key, peer: "Peer") -> "Peer":
    """Replace an existing peer entry (if any) with a new one under lock."""
    with node.peers_lock:
        node.peers.pop(old_key, None)
        node.peers[peer_key] = peer
    return peer


def get_peer(node: "Node", peer_key):
    """Retrieve a peer entry under lock."""
    with node.peers_lock:
        return node.peers.get(peer_key)


def remove_peer(node: "Node", peer_key):
    """Remove a peer entry under lock."""
    with node.peers_lock:
        return node.peers.pop(peer_key, None)
