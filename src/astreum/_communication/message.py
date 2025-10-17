from enum import IntEnum
from typing import Optional
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

class MessageTopic(IntEnum):
    PING = 0
    OBJECT_REQUEST = 1
    OBJECT_RESPONSE = 2
    ROUTE_REQUEST = 3
    ROUTE_RESPONSE = 4
    TRANSACTION = 5
    

class Message:
    handshake: bool
    sender: Optional[X25519PublicKey]

    topic: Optional[MessageTopic]
    content: bytes

    def __init__(
        self,
        *,
        handshake: bool = False,
        sender: Optional[X25519PublicKey] = None,
        topic: Optional[MessageTopic] = None,
        content: bytes = b"",
        body: Optional[bytes] = None,
    ) -> None:
        if body is not None:
            if content and content != b"":
                raise ValueError("specify only one of 'content' or 'body'")
            content = body

        self.handshake = handshake
        self.sender = sender
        self.topic = topic
        self.content = content or b""

        if self.handshake:
            if self.sender is None:
                raise ValueError("handshake Message requires a sender public key")
            self.topic = None
            self.content = b""
        else:
            if self.topic is None:
                raise ValueError("non-handshake Message requires a topic")

    def to_bytes(self):
        if self.handshake:
            # handshake byte (1) + raw public key bytes
            return bytes([1]) + self.sender.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
        else:
            # normal message: 0 + topic + content
            return bytes([0, self.topic.value]) + self.content

    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        if len(data) < 1:
            raise ValueError("Cannot parse Message: no data")
        flag = data[0]
        # create empty instance
        msg = cls.__new__(cls)

        if flag == 1:
            # handshake message: the rest is the peer’s public key
            key_bytes = data[1:]
            if not key_bytes:
                raise ValueError("Handshake message missing sender public key bytes")
            try:
                sender = X25519PublicKey.from_public_bytes(key_bytes)
            except ValueError:
                raise ValueError("Invalid public key bytes")
            if sender is None:
                raise ValueError("Handshake message missing sender public key")
            msg.handshake = True
            msg.sender = sender
            msg.topic = None
            msg.content = b''
        elif flag == 0:
            # normal message: next byte is topic, rest is content
            if len(data) < 2:
                raise ValueError("Cannot parse Message: missing topic byte")
            topic_val = data[1]
            try:
                topic = MessageTopic(topic_val)
            except ValueError:
                raise ValueError(f"Unknown MessageTopic: {topic_val}")
            msg.handshake = False
            msg.sender = None
            msg.topic = topic
            msg.content = data[2:]
        else:
            raise ValueError(f"Invalid handshake flag: {flag}")

        return msg
