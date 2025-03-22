# EdDSA signature algorithm over Curve25519

# ed25519.py
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from typing import Tuple

def generate_key_pair() -> Tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """
    Generate an Ed25519 private and public key pair.
    
    Returns:
        Tuple[Ed25519PrivateKey, Ed25519PublicKey]: The generated key pair.
    """
    private_key: Ed25519PrivateKey = ed25519.Ed25519PrivateKey.generate()
    public_key: Ed25519PublicKey = private_key.public_key()
    return private_key, public_key

def sign_message(private_key: Ed25519PrivateKey, message: bytes) -> bytes:
    """
    Sign a message using the provided Ed25519 private key.
    
    Args:
        private_key (Ed25519PrivateKey): The private key used for signing.
        message (bytes): The message to sign.
    
    Returns:
        bytes: The signature.
    """
    signature: bytes = private_key.sign(message)
    return signature

def verify_signature(public_key: Ed25519PublicKey, message: bytes, signature: bytes) -> bool:
    """
    Verify a message signature using the provided Ed25519 public key.
    
    Args:
        public_key (Ed25519PublicKey): The public key corresponding to the private key that signed.
        message (bytes): The original message.
        signature (bytes): The signature to verify.
        
    Returns:
        bool: True if the signature is valid, False otherwise.
    """
    try:
        public_key.verify(signature, message)
        return True
    except InvalidSignature:
        return False
