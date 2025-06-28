# Diffie-Hellman key exchange over Curve25519

# x25519.py
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from typing import Tuple

def generate_key_pair() -> Tuple[X25519PrivateKey, X25519PublicKey]:
    """
    Generate an X25519 private and public key pair.
    
    Returns:
        Tuple[X25519PrivateKey, X25519PublicKey]: The generated key pair.
    """
    private_key: X25519PrivateKey = x25519.X25519PrivateKey.generate()
    public_key: X25519PublicKey = private_key.public_key()
    return private_key, public_key

def generate_shared_key(private_key: X25519PrivateKey, peer_public_key: X25519PublicKey) -> bytes:
    """
    Generate a shared key using the provided private key and peer's public key.
    
    Args:
        private_key (X25519PrivateKey): Our private key.
        peer_public_key (X25519PublicKey): The peer's public key.
        
    Returns:
        bytes: The shared key.
    """
    shared_key: bytes = private_key.exchange(peer_public_key)
    return shared_key
