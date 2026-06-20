import unittest
import threading
import time
from unittest.mock import MagicMock
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519

from astreum import Node
from astreum.communication.models.message import Message, MessageTopic
from astreum.communication.processors.incoming import process_incoming_messages

class TestIntegrationPortHandling(unittest.TestCase):
    def test_peer_discovery_uses_source_port(self):
        """
        Verify that when a message is received, the Peer object
        uses the UDP source port (addr[1]) rather than any advertised port.
        """
        node = MagicMock(spec=Node)
        node.relay_secret_key = x25519.X25519PrivateKey.generate()
        node.relay_public_key = node.relay_secret_key.public_key()
        node.relay_public_key_bytes = node.relay_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        node.config = {"port": 9999}
        node.peers = {}
        node.incoming_queue = __import__('queue').Queue()
        node.outgoing_queue = __import__('queue').Queue()
        node.communication_stop_event = threading.Event()
        node.logger = MagicMock()
        node.get_peer.side_effect = lambda k: node.peers.get(k)
        node.peer_route = MagicMock()
        node.default_seed_ips = []

        sender_private_key = x25519.X25519PrivateKey.generate()
        sender_public_key = sender_private_key.public_key()
        sender_bytes = sender_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

        shared_key = sender_private_key.exchange(node.relay_public_key)

        msg = Message(
            handshake=False,
            sender=sender_public_key,
            topic=MessageTopic.PING,
            content=b"ping"
        )
        msg.encrypt(shared_key)
        msg_bytes = msg.to_bytes()

        # Simulate receiving from ephemeral port 54321
        ephemeral_port = 54321
        sender_host = "127.0.0.1"
        node.incoming_queue.put((msg_bytes, (sender_host, ephemeral_port), len(msg_bytes)))

        with unittest.mock.patch('astreum.communication.processors.incoming.handle_ping') as mock_handle_ping:
            t = threading.Thread(target=process_incoming_messages, args=(node,))
            t.start()

            time.sleep(0.2)
            node.communication_stop_event.set()
            t.join(timeout=1.0)

            self.assertTrue(mock_handle_ping.called, "handle_ping should have been called")

            args, _ = mock_handle_ping.call_args
            peer_obj = args[1]
            # Must use the UDP source port, not any advertised port
            self.assertEqual(peer_obj.address, (sender_host, ephemeral_port))

            self.assertNotIn(sender_bytes, node.peers)
            node.peer_route.add_peer.assert_not_called()

    def test_peer_address_updated_uses_source_port(self):
        """
        Verify that an existing peer's address is updated using the
        UDP source port when a message arrives.
        """
        node = MagicMock(spec=Node)
        node.relay_secret_key = x25519.X25519PrivateKey.generate()
        node.relay_public_key = node.relay_secret_key.public_key()
        node.relay_public_key_bytes = node.relay_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        node.config = {"port": 9999}
        node.incoming_queue = __import__('queue').Queue()
        node.communication_stop_event = threading.Event()
        node.logger = MagicMock()

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

        new_host = "2.2.2.2"
        msg = Message(
            topic=MessageTopic.PING,
            sender=sender_public_key,
            content=b"ping"
        )
        msg.encrypt(shared_key)
        msg_bytes = msg.to_bytes()

        # Received from source port 54321
        node.incoming_queue.put((msg_bytes, (new_host, 54321), len(msg_bytes)))

        with unittest.mock.patch('astreum.communication.processors.incoming.handle_ping'):
            t = threading.Thread(target=process_incoming_messages, args=(node,))
            t.start()
            time.sleep(0.2)
            node.communication_stop_event.set()
            t.join(timeout=1.0)

            # Must update to the UDP source port (54321), not any advertised port
            self.assertEqual(peer.address, (new_host, 54321))

if __name__ == '__main__':
    unittest.main()
