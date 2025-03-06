"""
Relay module for handling network communication in the Astreum node.
"""

import socket
import threading
from queue import Queue
from typing import Tuple, Callable, Dict
from .message import Message, Topic
from .envelope import Envelope
from .bucket import KBucket
from .peer import Peer, PeerManager
from .route import RouteTable

class Relay:
    def __init__(self, config: dict):
        self.use_ipv6 = config.get('use_ipv6', False)
        incoming_port = config.get('incoming_port', 7373)
        self.max_message_size = config.get('max_message_size', 65536)  # Max UDP datagram size
        self.num_workers = config.get('num_workers', 4)

        # Choose address family based on IPv4 or IPv6
        family = socket.AF_INET6 if self.use_ipv6 else socket.AF_INET

        # Create a UDP socket
        self.incoming_socket = socket.socket(family, socket.SOCK_DGRAM)

        # Allow dual-stack support (IPv4-mapped addresses on IPv6)
        if self.use_ipv6:
            self.incoming_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)

        # Bind to an address (IPv6 "::" or IPv4 "0.0.0.0") and port
        bind_address = "::" if self.use_ipv6 else "0.0.0.0"
        self.incoming_socket.bind((bind_address, incoming_port or 0))

        # Get the actual port assigned
        self.incoming_port = self.incoming_socket.getsockname()[1]

        # Create a UDP socket for sending messages
        self.outgoing_socket = socket.socket(family, socket.SOCK_DGRAM)

        # Message queues
        self.incoming_queue = Queue()
        self.outgoing_queue = Queue()
        
        # Message handling
        self.message_handlers: Dict[Topic, Callable] = {}

        # Start worker threads
        self._start_workers()
        
    def register_message_handler(self, topic: Topic, handler_func):
        """Register a handler function for a specific message topic."""
        self.message_handlers[topic] = handler_func

    def _start_workers(self):
        """Start worker threads for processing incoming and outgoing messages."""
        self.running = True
        
        # Start receiver thread
        self.receiver_thread = threading.Thread(target=self._receive_messages)
        self.receiver_thread.daemon = True
        self.receiver_thread.start()

        # Start sender thread
        self.sender_thread = threading.Thread(target=self._send_messages)
        self.sender_thread.daemon = True
        self.sender_thread.start()

        # Start worker threads for processing incoming messages
        self.worker_threads = []
        for _ in range(self.num_workers):
            thread = threading.Thread(target=self._process_messages)
            thread.daemon = True
            thread.start()
            self.worker_threads.append(thread)

    def _receive_messages(self):
        """Continuously receive messages and add them to the incoming queue."""
        while self.running:
            try:
                data, addr = self.incoming_socket.recvfrom(self.max_message_size)
                self.incoming_queue.put((data, addr))
            except Exception as e:
                # Log error but continue running
                print(f"Error receiving message: {e}")

    def _send_messages(self):
        """Continuously send messages from the outgoing queue."""
        while self.running:
            try:
                data, addr = self.outgoing_queue.get()
                self.outgoing_socket.sendto(data, addr)
                self.outgoing_queue.task_done()
            except Exception as e:
                # Log error but continue running
                print(f"Error sending message: {e}")

    def _process_messages(self):
        """Process messages from the incoming queue."""
        while self.running:
            try:
                data, addr = self.incoming_queue.get()
                self._handle_message(data, addr)
                self.incoming_queue.task_done()
            except Exception as e:
                # Log error but continue running
                print(f"Error processing message: {e}")

    def _handle_message(self, data: bytes, addr: Tuple[str, int]):
        """Handle an incoming message."""
        envelope = Envelope.from_bytes(data)
        if envelope and envelope.message.topic in self.message_handlers:
            self.message_handlers[envelope.message.topic](envelope.message.body, addr, envelope)

    def send(self, data: bytes, addr: Tuple[str, int]):
        """Send raw data to a specific address."""
        self.outgoing_queue.put((data, addr))
        
    def send_message(self, body: bytes, topic: Topic, addr: Tuple[str, int], encrypted: bool = False, difficulty: int = 1):
        """
        Create and send a message to a specific address.
        
        Args:
            body (bytes): The message body
            topic (Topic): The message topic
            addr (Tuple[str, int]): The recipient's address (host, port)
            encrypted (bool): Whether the message is encrypted
            difficulty (int): Number of leading zero bits required in the nonce hash
        """
        envelope = Envelope.create(body, topic, encrypted, difficulty)
        encoded_data = envelope.to_bytes()
        self.send(encoded_data, addr)

    def stop(self):
        """Stop all worker threads."""
        self.running = False
        # Wait for queues to be processed
        self.incoming_queue.join()
        self.outgoing_queue.join()
