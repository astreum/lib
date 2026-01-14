
import unittest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from astreum.communication.models.message import Message, MessageTopic

class TestMessagePort(unittest.TestCase):
    def setUp(self):
        self.private_key = x25519.X25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        self.sender_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

    def test_handshake_message_with_port(self):
        port = 8080
        msg = Message(
            handshake=True,
            sender=self.public_key,
            incoming_port=port,
            content=b"hello"
        )
        
        encoded = msg.to_bytes()
        # 1 byte type + 32 bytes sender + 2 bytes port + 5 bytes content = 40 bytes
        self.assertEqual(len(encoded), 40)
        self.assertEqual(encoded[33:35], port.to_bytes(2, "big"))

        decoded = Message.from_bytes(encoded)
        self.assertEqual(decoded.incoming_port, port)
        self.assertTrue(decoded.handshake)
        self.assertEqual(decoded.content, b"hello")

    def test_handshake_message_without_port(self):
        msg = Message(
            handshake=True,
            sender=self.public_key,
            content=b"hello"
        )
        
        encoded = msg.to_bytes()
        self.assertEqual(len(encoded), 40)
        self.assertEqual(encoded[33:35], b"\x00\x00")

        decoded = Message.from_bytes(encoded)
        self.assertIsNone(decoded.incoming_port)
        self.assertTrue(decoded.handshake)

    def test_normal_message_with_port(self):
        # Normal message requires encryption which we mock here for simple structure test
        # Normally from_bytes expects encrypted payload
        port = 1234
        # Manually constructing what to_bytes produces for normal message:
        # 0 (1) + sender (32) + port (2) + encrypted (variable)
        encrypted_payload = b"nonce+ciphertext"
        
        encoded = bytes([0]) + self.sender_bytes + port.to_bytes(2, "big") + encrypted_payload
        
        decoded = Message.from_bytes(encoded)
        self.assertEqual(decoded.incoming_port, port)
        self.assertFalse(decoded.handshake)
        self.assertEqual(decoded.encrypted, encrypted_payload)

        # Confirm to_bytes matches this structure if we bypass the encrypt() check or mock it
        msg = Message(
            handshake=False,
            sender=self.public_key,
            incoming_port=port,
            topic=MessageTopic.PING,
            encrypted=encrypted_payload
        )
        self.assertEqual(msg.to_bytes(), encoded)

    def test_invalid_length(self):
        # Too short for header
        data = bytes([1]) + self.sender_bytes + b"\x00" # 34 bytes
        with self.assertRaisesRegex(ValueError, "missing header bytes"):
            Message.from_bytes(data)

if __name__ == '__main__':
    unittest.main()
