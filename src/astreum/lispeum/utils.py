"""
Utility functions for the Lispeum module.
"""

import blake3

def hash_data(data: bytes) -> bytes:
    """
    Hash data using BLAKE3.
    
    Args:
        data: Data to hash
        
    Returns:
        32-byte BLAKE3 hash
    """
    return blake3.blake3(data).digest()
