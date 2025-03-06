"""
Message related classes and utilities for Astreum node network.
"""

import struct
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional
from astreum.utils.bytes_format import encode, decode

class Topic(Enum):
    """
    Enum for different message topics in the Astreum network.
    """
    OBJECT_REQUEST = auto()
    OBJECT = auto()
    PING = auto()
    PONG = auto()
    ROUTE = auto()
    ROUTE_REQUEST = auto()
    LATEST_BLOCK = auto()
    BLOCK = auto()
    LATEST_BLOCK_REQUEST = auto()
    TRANSACTION = auto()
    
    def to_bytes(self) -> bytes:
        """
        Convert this Topic enum value to bytes.
        
        Returns:
            bytes: Single byte representing the topic
        """
        return struct.pack('!B', self.value)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> Optional['Topic']:
        """
        Create a Topic from its serialized form.
        
        Args:
            data (bytes): Serialized topic (single byte)
            
        Returns:
            Optional[Topic]: The deserialized topic, or None if the data is invalid
        """
        if not data or len(data) != 1:
            return None
            
        try:
            topic_value = struct.unpack('!B', data)[0]
            return cls(topic_value)
        except (struct.error, ValueError) as e:
            print(f"Error deserializing topic: {e}")
            return None

@dataclass
class Message:
    """
    Represents a message in the Astreum network.
    
    Attributes:
        body (bytes): The actual content of the message
        topic (Topic): The topic/type of the message
    """
    body: bytes
    topic: Topic
    
    def to_bytes(self) -> bytes:
        """
        Convert this Message to bytes using bytes_format.
        
        Returns:
            bytes: Serialized message
        """
        return encode([
            self.topic.to_bytes(),
            self.body
        ])
    
    @classmethod
    def from_bytes(cls, data: bytes) -> Optional['Message']:
        """
        Create a Message from its serialized form using bytes_format.
        
        Args:
            data (bytes): Serialized message
            
        Returns:
            Optional[Message]: The deserialized message, or None if the data is invalid
        """
        try:
            parts = decode(data)
            if len(parts) != 2:
                return None
                
            topic_data, body = parts
            topic = Topic.from_bytes(topic_data)
            
            if not topic:
                return None
                
            return cls(body=body, topic=topic)
        except (ValueError, struct.error) as e:
            print(f"Error deserializing message: {e}")
            return None
