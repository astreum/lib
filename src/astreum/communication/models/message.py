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
    STORAGE_REQUEST = 6


class Message:
    handshake: bool
    sender_bytes: bytes

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
        sender_bytes: Optional[bytes] = None,
    ) -> None:
        if body is not None:
            if content and content != b"":
                raise ValueError("specify only one of 'content' or 'body'")
            content = body

        self.handshake = handshake
        self.topic = topic
        self.content = content or b""

        if self.handshake:
            if sender_bytes is None and sender is None:
                raise ValueError("handshake Message requires a sender public key or sender bytes")
            self.topic = None
            self.content = b""
        else:
            if self.topic is None:
                raise ValueError("non-handshake Message requires a topic")
            if sender_bytes is None and sender is None:
                raise ValueError("non-handshake Message requires a sender public key or sender bytes")

        if sender_bytes is not None:
            self.sender_bytes = sender_bytes
        else:
            if sender is None:
                raise ValueError("sender public key required to derive sender bytes")
            self.sender_bytes = sender.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )

    def to_bytes(self):
        if self.handshake:
            # handshake byte (1) + raw public key bytes
            return bytes([1]) + self.sender_bytes
        else:
            # normal message: 0 + sender + topic + content
            if not self.sender_bytes:
                raise ValueError("non-handshake Message missing sender public key bytes")
            # new wire format: flag + sender + topic + content
            return bytes([0]) + self.sender_bytes + bytes([self.topic.value]) + self.content

    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        if len(data) < 1:
            raise ValueError("Cannot parse Message: no data")
        

        handshake = data[0] == 1

        if len(data) < 33:
            raise ValueError("Cannot parse Message: missing sender bytes")

        sender_bytes = data[1:33]

        if handshake:

            return Message(
                handshake=True,
                sender_bytes=sender_bytes,
            )

        else:

            topic = MessageTopic(data[33])

            content = data[34:]

            return Message(
                handshake=False,
                topic=topic,
                content=content,
                sender_bytes=sender_bytes,
            )
