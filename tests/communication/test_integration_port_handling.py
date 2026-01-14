import unittest
import threading
import socket
import time
from unittest.mock import MagicMock
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519

from astreum import Node
from astreum.communication.models.message import Message, MessageTopic
from astreum.communication.processors.incoming import process_incoming_messages
from astreum.communication.outgoing_queue import enqueue_outgoing

class TestIntegrationPortHandling(unittest.TestCase):
    def test_peer_discovery_with_explicit_port(self):
        """
        Verify that when a message is received from an ephemeral port
        but contains an explicit incoming_port in the header,
        the created Peer object uses the explicit port.
        """
        # Mock node
        node = MagicMock(spec=Node)
        node.relay_secret_key = x25519.X25519PrivateKey.generate()
        node.relay_public_key = node.relay_secret_key.public_key()
        node.relay_public_key_bytes = node.relay_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        node.config = {"incoming_port": 9999}
        node.peers = {}
        node.incoming_queue = __import__('queue').Queue()
        node.outgoing_queue = __import__('queue').Queue()
        node.outgoing_queue_size = 0
        node.outgoing_queue_size_limit = 1000
        node.outgoing_queue_size_lock = threading.Lock()
        node.communication_stop_event = threading.Event()
        node.logger = MagicMock()
        node.get_peer.side_effect = lambda k: node.peers.get(k)
        node.peer_route = MagicMock()
        node.default_seed_ips = []
        
        # Sender identity
        sender_private_key = x25519.X25519PrivateKey.generate()
        sender_public_key = sender_private_key.public_key()
        sender_bytes = sender_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        # Calculate shared key for encryption
        shared_key = sender_private_key.exchange(node.relay_public_key)
        
        # Construct a PING message with explicit port 8080
        listening_port = 8080
        msg = Message(
            handshake=False,
            sender=sender_public_key,
            incoming_port=listening_port,
            topic=MessageTopic.PING,
            content=b"ping"
        )
        msg.encrypt(shared_key)
        msg_bytes = msg.to_bytes()
        
        # Simulate receiving this message from an ephemeral port (e.g. 54321)
        ephemeral_port = 54321
        sender_host = "127.0.0.1"
        node.incoming_queue.put((msg_bytes, (sender_host, ephemeral_port), len(msg_bytes)))
        
        # Patch handle_ping to verify the peer passed to it
        with unittest.mock.patch('astreum.communication.processors.incoming.handle_ping') as mock_handle_ping:
            t = threading.Thread(target=process_incoming_messages, args=(node,))
            t.start()
            
            time.sleep(0.2)
            node.communication_stop_event.set()
            t.join(timeout=1.0)
            
            # Verify handle_ping was called
            self.assertTrue(mock_handle_ping.called, "handle_ping should have been called")
            
            # Verify the peer passed to handle_ping has the listening port
            args, _ = mock_handle_ping.call_args
            # args: (node, peer, content)
            peer_obj = args[1]
            self.assertEqual(peer_obj.address, (sender_host, listening_port))
            
            # CRITICAL VERIFICATION: The peer should NOT be in the node's registry
            # because it was a PING, not a handshake.
            self.assertNotIn(sender_bytes, node.peers)
            node.peer_route.add_peer.assert_not_called()

    def test_outgoing_queue_injects_port(self):
        """
        Verify that enqueue_outgoing injects the node's configured incoming_port
        into the message if it's missing.
        """
        node = MagicMock(spec=Node)
        node.config = {"incoming_port": 7777}
        node.is_connected = True
        node.outgoing_queue = __import__('queue').Queue()
        node.outgoing_queue_size_lock = threading.Lock()
        node.outgoing_queue_size = 0
        node.outgoing_queue_size_limit = 1000
        node.outgoing_queue_timeout = 1.0
        node.communication_stop_event = threading.Event()
        node.logger = MagicMock()
        
        # Provide sender for valid Message init
        sender_key = x25519.X25519PrivateKey.generate().public_key()
        msg = Message(
            topic=MessageTopic.PING,
            sender=sender_key,
            encrypted=b"dummy_encrypted" # satisfy strict checks if any
        )

        # Call enqueue
        enqueue_outgoing(node, ("1.2.3.4", 5555), message=msg)
        
        # Check the queued payload
        self.assertEqual(msg.incoming_port, 7777)


    def test_message_without_port_ignored(self):
        """
        Verify that a message with a 0/None incoming_port is ignored.
        """
        node = MagicMock(spec=Node)
        node.relay_secret_key = x25519.X25519PrivateKey.generate()
        node.relay_public_key = node.relay_secret_key.public_key()
        node.config = {"incoming_port": 9999}
        node.incoming_queue = __import__('queue').Queue()
        node.communication_stop_event = threading.Event()
        node.logger = MagicMock()
        node.get_peer.return_value = None
        
        # Sender identity
        sender_private_key = x25519.X25519PrivateKey.generate()
        sender_public_key = sender_private_key.public_key()
        shared_key = sender_private_key.exchange(node.relay_public_key)
        
        # Message with PORT = 0 (interpreted as None)
        msg = Message(
            topic=MessageTopic.PING,
            sender=sender_public_key,
            incoming_port=None, # will be 0 in bytes
            content=b"ping"
        )
        msg.encrypt(shared_key)
        msg_bytes = msg.to_bytes()
        
        node.incoming_queue.put((msg_bytes, ("127.0.0.1", 54321), len(msg_bytes)))
        
        with unittest.mock.patch('astreum.communication.processors.incoming.handle_ping') as mock_handle_ping:
            t = threading.Thread(target=process_incoming_messages, args=(node,))
            t.start()
            time.sleep(0.2)
            node.communication_stop_event.set()
            t.join(timeout=1.0)
            
            self.assertFalse(mock_handle_ping.called, "handle_ping should NOT be called for message without port")
            # Verify a warning was logged
            node.logger.warning.assert_called()
            args, _ = node.logger.warning.call_args
            self.assertIn("missing incoming_port", args[0])

    def test_peer_address_updated_on_message(self):
        """
        Verify that an existing peer's address is updated if a new message
        arrives from a different IP or with a different incoming_port.
        """
        node = MagicMock(spec=Node)
        node.relay_secret_key = x25519.X25519PrivateKey.generate()
        node.relay_public_key = node.relay_secret_key.public_key()
        node.config = {"incoming_port": 9999}
        node.incoming_queue = __import__('queue').Queue()
        node.communication_stop_event = threading.Event()
        node.logger = MagicMock()
        
        # Sender identity
        sender_private_key = x25519.X25519PrivateKey.generate()
        sender_public_key = sender_private_key.public_key()
        sender_bytes = sender_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        shared_key = sender_private_key.exchange(node.relay_public_key)
        
        # Existing peer at 1.1.1.1:1111
        peer = MagicMock()
        peer.address = ("1.1.1.1", 1111)
        peer.shared_key_bytes = shared_key
        node.get_peer.return_value = peer
        
        # New message from 2.2.2.2 with port 2222
        listening_port = 2222
        new_host = "2.2.2.2"
        msg = Message(
            topic=MessageTopic.PING,
            sender=sender_public_key,
            incoming_port=listening_port,
            content=b"ping"
        )
        msg.encrypt(shared_key)
        msg_bytes = msg.to_bytes()
        
        node.incoming_queue.put((msg_bytes, (new_host, 54321), len(msg_bytes)))
        
        with unittest.mock.patch('astreum.communication.processors.incoming.handle_ping'):
            t = threading.Thread(target=process_incoming_messages, args=(node,))
            t.start()
            time.sleep(0.2)
            node.communication_stop_event.set()
            t.join(timeout=1.0)
            
            # Verify peer address was updated
            self.assertEqual(peer.address, (new_host, listening_port))

if __name__ == '__main__':
    unittest.main()
