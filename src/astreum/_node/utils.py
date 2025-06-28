"""
Utility functions for the Astreum blockchain.
"""

import blake3

def blake3_hash(data: bytes) -> bytes:
    """
    Hash data using BLAKE3.
    
    Args:
        data: Data to hash
        
    Returns:
        32-byte BLAKE3 hash
    """
    return blake3.blake3(data).digest()

def hash_object(obj) -> bytes:
    """
    Hash a Python object by converting it to a string and then hashing.
    
    Args:
        obj: Python object to hash
        
    Returns:
        32-byte BLAKE3 hash
    """
    if isinstance(obj, bytes):
        return hash_data(obj)
    elif isinstance(obj, str):
        return hash_data(obj.encode('utf-8'))
    else:
        return hash_data(str(obj).encode('utf-8'))
