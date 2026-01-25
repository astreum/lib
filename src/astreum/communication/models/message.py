import os
from enum import IntEnum
from typing import Optional
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
from astreum.crypto import chacha20poly1305

class MessageTopic(IntEnum):
    PING = 0
    OBJECT_REQUEST = 1
    OBJECT_RESPONSE = 2
    ROUTE_REQUEST = 3
    ROUTE_RESPONSE = 4
    TRANSACTION = 5


class Message:
    def __init__(
        self,
        *,
        handshake: bool = False,
        sender: Optional[X25519PublicKey] = None,
        topic: Optional[MessageTopic] = None,
        content: Optional[bytes] = None,
        body: Optional[bytes] = None,
        sender_public_key_bytes: Optional[bytes] = None,
        encrypted: Optional[bytes] = None,
        incoming_port: Optional[int] = None,
    ) -> None:
        if body is not None:
            if content is not None and content != b"":
                raise ValueError("specify only one of 'content' or 'body'")
            content = body

        self.handshake = handshake
        self.topic = topic
        self.content = content if content is not None else b""
        self.encrypted = encrypted
        self.incoming_port = incoming_port

        if self.handshake:
            if sender_public_key_bytes is None and sender is None:
                raise ValueError("handshake Message requires a sender public key or sender public key bytes")
            self.topic = None
        else:
            if self.topic is None and self.encrypted is None:
                raise ValueError("non-handshake Message requires a topic or encrypted payload")
            if sender_public_key_bytes is None and sender is None:
                raise ValueError("non-handshake Message requires a sender public key or sender public key bytes")

        if sender_public_key_bytes is not None:
            self.sender_public_key_bytes = sender_public_key_bytes
        else:
            if sender is None:
                raise ValueError("sender public key required to derive sender public key bytes")
            self.sender_public_key_bytes = sender.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )

    def to_bytes(self):
        port_bytes = (
            self.incoming_port.to_bytes(2, "big")
            if self.incoming_port
            else b"\x00\x00"
        )
        if self.handshake:
            # handshake byte (1) + raw public key bytes + port + payload
            return bytes([1]) + self.sender_public_key_bytes + port_bytes + self.content
        else:
            # normal message: 0 + sender + port + encrypted payload (nonce + ciphertext)
            if not self.encrypted:
                raise ValueError("non-handshake Message missing encrypted payload; call encrypt() first")
            return bytes([0]) + self.sender_public_key_bytes + port_bytes + self.encrypted

    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        if len(data) < 1:
            raise ValueError("Cannot parse Message: no data")

        # 1 byte type + 32 bytes sender + 2 bytes port = 35 bytes min
        if len(data) < 35:
            raise ValueError("Cannot parse Message: missing header bytes")

        incoming_port = int.from_bytes(data[33:35], "big")
        if incoming_port == 0:
            incoming_port = None

        if data[0] == 1:
            return Message(
                handshake=True,
                sender_public_key_bytes=data[1:33],
                incoming_port=incoming_port,
                content=data[35:],
            )

        else:
            if len(data) <= 35:
                raise ValueError("Cannot parse Message: missing encrypted payload")

            return Message(
                handshake=False,
                sender_public_key_bytes=data[1:33],
                incoming_port=incoming_port,
                encrypted=data[35:],
            )

    def encrypt(self, shared_key_bytes: bytes) -> None:
        if self.handshake:
            return
        
        if len(shared_key_bytes) != 32:
            raise ValueError("Shared key must be 32 bytes for ChaCha20-Poly1305")
        
        if self.topic is None:
            raise ValueError("Cannot encrypt message without a topic")

        nonce = os.urandom(12)
        data_to_encrypt = bytes([self.topic.value]) + self.content
        ciphertext = chacha20poly1305.encrypt(shared_key_bytes, nonce, data_to_encrypt)
        self.encrypted = nonce + ciphertext

    def decrypt(self, shared_key_bytes: bytes) -> None:
        if self.handshake:
            return
        
        if len(shared_key_bytes) != 32:
            raise ValueError("Shared key must be 32 bytes for ChaCha20-Poly1305")
        
        if not self.encrypted or len(self.encrypted) < 13:
            raise ValueError("Encrypted content missing or too short")

        nonce = self.encrypted[:12]
        ciphertext = self.encrypted[12:]
        decrypted = chacha20poly1305.decrypt(shared_key_bytes, nonce, ciphertext)
        topic_value = decrypted[0]
        self.topic = MessageTopic(topic_value)
        self.content = decrypted[1:]
