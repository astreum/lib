"""
Envelope related classes and utilities for Astreum node network.

Message Structure:
                    + - - - - - - - +
                    |   Envelope    |
                    + - - - - - - - +
                            ^
                    . - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - .
                    ^                       ^                       ^                       ^
            + - - - - - - - +       + - - - - - - - +       + - - - - - - - +       + - - - - - - - +
            |     Time      |       |   Encrypted   |       |     Nonce     |       |    Message    |
            + - - - - - - - +       + - - - - - - - +       + - - - - - - - +       + - - - - - - - +
                                                                                            ^
                                                                                . - - - - - - - - - - - .
                                                                                ^                       ^
                                                                         + - - - - - - - +       + - - - - - - - +
                                                                         |     Topic     |       |     Body      |
                                                                         + - - - - - - - +       + - - - - - - - +

The Envelope uses a Merkle tree structure with the following leaves:
- Timestamp
- Encrypted flag
- Nonce
- Message bytes

The root hash of this Merkle tree must have a specified number of leading zero bits,
determined by the difficulty parameter. The nonce is adjusted until this requirement is met.
"""

import struct
import time
import os
from dataclasses import dataclass
from typing import Optional, Tuple, List
from .message import Message, Topic
from astreum.format import encode, decode
from ..utils import hash_data

@dataclass
class Envelope:
    """
    Represents an envelope that wraps a message with additional metadata.
    
    Attributes:
        encrypted (bool): True if the message is encrypted, False otherwise
        message (Message): The message being sent
        nonce (bytes): Nonce for encryption and proof of work
        timestamp (int): Time when the envelope was created
    """
    encrypted: bool
    message: Message
    nonce: bytes
    timestamp: int
    
    @classmethod
    def create(cls, body: bytes, topic: Topic, encrypted: bool = False, difficulty: int = 1) -> 'Envelope':
        """
        Create a new envelope with the current timestamp and a nonce that satisfies
        the given difficulty level using a Merkle tree structure.
        
        Args:
            body (bytes): The message body
            topic (Topic): The message topic
            encrypted (bool): Whether the message is encrypted
            difficulty (int): Number of leading zero bits required in the Merkle root hash
            
        Returns:
            Envelope: A new envelope with a valid nonce
        """
        timestamp = int(time.time())
        message = Message(body=body, topic=topic)
        
        # Generate a valid nonce for the Merkle tree
        nonce = cls._generate_nonce(message, timestamp, encrypted, difficulty)
        
        return cls(
            encrypted=encrypted,
            message=message,
            nonce=nonce,
            timestamp=timestamp
        )
    
    @staticmethod
    def _generate_nonce(message: Message, timestamp: int, encrypted: bool, difficulty: int) -> bytes:
        """
        Generate a nonce that results in a Merkle tree root hash with the specified
        number of leading zero bits.
        
        Args:
            message (Message): The message to include in the Merkle tree
            timestamp (int): The timestamp to include in the Merkle tree
            encrypted (bool): Whether the message is encrypted
            difficulty (int): Number of leading zero bits required
            
        Returns:
            bytes: A valid nonce
        """
        # Prepare the message data
        message_data = message.to_bytes()
        timestamp_data = struct.pack('!Q', timestamp)
        encrypted_flag = b'\x01' if encrypted else b'\x00'
        
        # Calculate how many bytes need to be zero
        zero_bytes = difficulty // 8
        # Calculate how many bits in the last byte need to be zero
        remaining_bits = difficulty % 8
        
        # Create a mask for the remaining bits
        mask = 0
        if remaining_bits > 0:
            mask = 0xFF >> remaining_bits
        
        while True:
            # Generate a random nonce
            nonce = os.urandom(32)
            
            # Calculate the Merkle root using the leaves
            merkle_root = Envelope._calculate_merkle_root([
                timestamp_data,
                encrypted_flag,
                nonce,
                message_data
            ])
            
            # Check if it meets the difficulty requirement
            valid = True
            
            # Check full zero bytes
            for i in range(zero_bytes):
                if merkle_root[i] != 0:
                    valid = False
                    break
            
            # If we need to check partial bits in a byte
            if valid and remaining_bits > 0:
                # The next byte should have required number of leading zeros
                if (merkle_root[zero_bytes] & (0xFF ^ mask)) != 0:
                    valid = False
            
            if valid:
                return nonce
    
    @staticmethod
    def _calculate_merkle_root(leaves: List[bytes]) -> bytes:
        """
        Calculate the Merkle root hash from a list of leaf node data.
        
        Args:
            leaves (List[bytes]): List of leaf node data
            
        Returns:
            bytes: The Merkle root hash
        """
        if not leaves:
            return hash_data(b'')
        
        if len(leaves) == 1:
            return hash_data(leaves[0])
            
        # Hash all leaf nodes
        hashed_leaves = [hash_data(leaf) for leaf in leaves]
        
        # Build the Merkle tree
        while len(hashed_leaves) > 1:
            if len(hashed_leaves) % 2 != 0:
                # Duplicate the last element if there's an odd number
                hashed_leaves.append(hashed_leaves[-1])
                
            # Combine adjacent pairs and hash them
            next_level = []
            for i in range(0, len(hashed_leaves), 2):
                combined = hashed_leaves[i] + hashed_leaves[i+1]
                next_level.append(hash_data(combined))
                
            hashed_leaves = next_level
            
        # Return the root hash
        return hashed_leaves[0]

    def verify_nonce(self, difficulty: int = 1) -> bool:
        """
        Verify that the nonce produces a valid Merkle tree root hash
        with the specified number of leading zero bits.
        
        Args:
            difficulty (int): Number of leading zero bits required in the root hash
        
        Returns:
            bool: True if the nonce is valid, False otherwise
        """
        # Prepare the message data
        message_data = self.message.to_bytes()
        timestamp_data = struct.pack('!Q', self.timestamp)
        encrypted_flag = b'\x01' if self.encrypted else b'\x00'
        
        # Calculate the Merkle root
        merkle_root = self._calculate_merkle_root([
            timestamp_data,
            encrypted_flag,
            self.nonce,
            message_data
        ])
        
        # Calculate how many bytes need to be zero
        zero_bytes = difficulty // 8
        # Calculate how many bits in the last byte need to be zero
        remaining_bits = difficulty % 8
        
        # Create a mask for the remaining bits
        mask = 0
        if remaining_bits > 0:
            mask = 0xFF >> remaining_bits
        
        # Check if it meets the difficulty requirement
        valid = True
        
        # Check full zero bytes
        for i in range(zero_bytes):
            if merkle_root[i] != 0:
                valid = False
                break
        
        # If we need to check partial bits in a byte
        if valid and remaining_bits > 0:
            # The next byte should have required number of leading zeros
            if (merkle_root[zero_bytes] & (0xFF ^ mask)) != 0:
                valid = False
        
        return valid
    
    def to_bytes(self) -> bytes:
        """
        Convert this Envelope to bytes.
        
        Returns:
            bytes: Serialized envelope
        """
        return encode([
            struct.pack('!Q', self.timestamp),
            b'\x01' if self.encrypted else b'\x00',
            self.nonce,
            self.message.to_bytes()
        ])
    
    @classmethod
    def from_bytes(cls, data: bytes) -> Optional['Envelope']:
        """
        Create an Envelope from its serialized form.
        
        Args:
            data (bytes): Serialized envelope
            
        Returns:
            Optional[Envelope]: The deserialized envelope, or None if the data is invalid
        """
        try:
            parts = decode(data)
            if len(parts) != 4:
                return None
                
            timestamp_data, encrypted_flag, nonce, message_data = parts
            
            timestamp = struct.unpack('!Q', timestamp_data)[0]
            encrypted = encrypted_flag == b'\x01'
            nonce = nonce
            message = Message.from_bytes(message_data)
            
            if not message:
                return None
                
            return cls(
                encrypted=encrypted,
                message=message,
                nonce=nonce,
                timestamp=timestamp
            )
        except (ValueError, struct.error) as e:
            print(f"Error deserializing envelope: {e}")
            return None
