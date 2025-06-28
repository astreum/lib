"""
Relay module for handling network communication in the Astreum node.
"""

import socket
import threading
import random
import time
from queue import Queue
from typing import Tuple, Callable, Dict, Set, Optional, List
from .message import Message, Topic
from .envelope import Envelope
from .bucket import KBucket
from .peer import Peer, PeerManager
from .route import RouteTable
import json
from cryptography.hazmat.primitives.asymmetric import ed25519

class Relay:
    def __init__(self, config: dict):
        """Initialize relay with configuration."""
        self.config = config
        self.use_ipv6 = config.get('use_ipv6', False)
        incoming_port = config.get('incoming_port', 7373)
        self.max_message_size = config.get('max_message_size', 65536)  # Max UDP datagram size
        self.num_workers = config.get('num_workers', 4)

        # Generate Ed25519 keypair for this node
        if 'relay_private_key' in config:
            # Load existing private key if provided
            try:
                private_key_bytes = bytes.fromhex(config['relay_private_key'])
                self.private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
            except Exception as e:
                print(f"Error loading private key: {e}, generating new one")
                self.private_key = ed25519.Ed25519PrivateKey.generate()
        else:
            # Generate new keypair
            self.private_key = ed25519.Ed25519PrivateKey.generate()
            
        # Use public key as node ID
        self.public_key = self.private_key.public_key()
        self.node_id = self.public_key.public_bytes_raw()
        
        # Save private key bytes for config persistence
        self.private_key_bytes = self.private_key.private_bytes_raw()

        # Routes that this node participates in 
        # 0 = peer route, 1 = validation route
        # All routes are tracked by default, but we only join some
        self.routes: List[int] = []
        self.tracked_routes: List[int] = [0, 1]  # Track all routes
        
        # Always join peer route
        self.routes.append(0)  # Peer route
            
        # Check if this node should join validation route
        if config.get('validation_route', False):
            self.routes.append(1)  # Validation route

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
        self.message_handlers: Dict[Topic, Callable] = {
            Topic.PEER_ROUTE: None,  # set by Node later
            Topic.OBJECT_REQUEST: None,  # set by Node later
            Topic.OBJECT_RESPONSE: None,  # set by Node later
        }

        # Route buckets (peers for each route)
        self.peer_route_bucket = KBucket(k=20)  # Bucket for peer route
        self.validation_route_bucket = KBucket(k=20)  # Bucket for validation route
        
        # Initialize route table with our node ID
        self.route_table = RouteTable(self)

        # Initialize storage index
        self.storage_index: Dict[bytes, bytes] = {}

        # Start worker threads
        self._start_workers()
        
    def is_in_peer_route(self) -> bool:
        """Check if this node is part of the peer route."""
        return 0 in self.routes
        
    def is_in_validation_route(self) -> bool:
        """Check if this node is part of the validation route."""
        return 1 in self.routes
    
    def is_tracking_route(self, route_type: int) -> bool:
        """Check if this node is tracking a specific route."""
        return route_type in self.tracked_routes
        
    def get_random_peers_from_route(self, route_type: int, count: int = 3) -> List[Peer]:
        """
        Get a list of random peers from different buckets in the specified route.
        
        Args:
            route_type (int): Route type (0 for peer, 1 for validation)
            count (int): Number of random peers to select (one from each bucket)
            
        Returns:
            List[Peer]: List of randomly selected peers from different buckets
        """
        result = []
        route_id = self._get_route_id(route_type)
        
        # Get all buckets that have peers for this route
        buckets_with_peers = []
        for i, bucket in enumerate(self.routing_table):
            # For each bucket, collect peers that are in this route
            route_peers_in_bucket = [peer for peer in bucket.values() 
                                    if peer.routes and route_id in peer.routes]
            if route_peers_in_bucket:
                buckets_with_peers.append((i, route_peers_in_bucket))
        
        # If we don't have any buckets with peers, return empty list
        if not buckets_with_peers:
            return []
        
        # If we have fewer buckets than requested count, adjust count
        sample_count = min(count, len(buckets_with_peers))
        
        # Sample random buckets
        selected_buckets = random.sample(buckets_with_peers, sample_count)
        
        # For each selected bucket, pick one random peer
        for bucket_idx, peers in selected_buckets:
            # Select one random peer from this bucket
            selected_peer = random.choice(peers)
            result.append(selected_peer)
            
        return result
        
    def get_peers_in_route(self, route_type: int) -> List[Peer]:
        """
        Get all peers in a specific route.
        
        Args:
            route_type (int): Route type (0 for peer, 1 for validation)
            
        Returns:
            List[Peer]: List of peers in the route
        """
        if route_type == 0:  # Peer route
            return self.peer_route_bucket.get_peers()
        elif route_type == 1:  # Validation route
            return self.validation_route_bucket.get_peers()
        return []
        
    def add_peer_to_route(self, peer: Peer, route_types: List[int]):
        """
        Add a peer to specified routes.
        
        Args:
            peer (Peer): The peer to add
            route_types (List[int]): List of route types to add the peer to (0 = peer, 1 = validation)
        """
        for route_type in route_types:
            if route_type == 0:  # Peer route
                # Add to top of bucket, eject last if at capacity
                self.peer_route_bucket.add(peer, to_front=True)
            elif route_type == 1:  # Validation route
                # Add to top of bucket, eject last if at capacity
                self.validation_route_bucket.add(peer, to_front=True)
            
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
            # For transaction messages, only process if we're in validation route
            if envelope.message.topic == Topic.TRANSACTION:
                if self.is_in_validation_route():
                    self.message_handlers[envelope.message.topic](envelope.message.body, addr, envelope)
            # For block messages, only process if we're in validation route
            elif envelope.message.topic == Topic.BLOCK:
                if self.is_in_validation_route():
                    self.message_handlers[envelope.message.topic](envelope.message.body, addr, envelope)
            # Latest block and latest block requests can be handled by any node tracking the routes
            elif envelope.message.topic in (Topic.LATEST_BLOCK, Topic.LATEST_BLOCK_REQUEST):
                self.message_handlers[envelope.message.topic](envelope.message.body, addr, envelope)
            # For other message types, always process
            else:
                self.message_handlers[envelope.message.topic](envelope.message.body, addr, envelope)

    def send(self, data: bytes, addr: Tuple[str, int]):
        """Send raw data to a specific address."""
        self.outgoing_queue.put((data, addr))
    
    def get_address(self) -> Tuple[str, int]:
        """
        Get the local address of this relay node.
        
        Returns:
            Tuple[str, int]: The local address (host, port)
        """
        # This is a simplification - in a real implementation this would determine the 
        # actual public-facing IP address, which may be different from the binding address
        return ("localhost", self.incoming_port)
        
    def get_routes(self) -> bytes:
        """
        Get the routes this node is part of as a bytes object.
        
        Returns:
            bytes: List of route types (0 for peer, 1 for validation)
        """
        return bytes(self.routes)
        
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

    def send_message_to_addr(self, addr: tuple, topic: Topic, body: bytes):
        """
        Send a message to a specific address.
        
        Args:
            addr: Tuple of (ip, port) to send to
            topic: Message topic
            body: Message body
        """
        try:
            # Create an envelope with our node id and the message
            message = Message(self.node_id, topic, body)
            envelope = Envelope(message)
            
            # Serialize and send
            self.outgoing_socket.sendto(envelope.to_bytes(), addr)
        except Exception as e:
            print(f"Error sending message to {addr}: {e}")
            
    def send_message_to_peer(self, peer: Peer, topic: Topic, body):
        """
        Send a message to a specific peer.
        
        Args:
            peer: Peer to send to
            topic: Message topic
            body: Message body (bytes or JSON serializable)
        """
        # Convert body to bytes if it's not already
        if not isinstance(body, bytes):
            if isinstance(body, dict) or isinstance(body, list):
                body = json.dumps(body).encode('utf-8')
            else:
                body = str(body).encode('utf-8')
                
        # Send to the peer's address
        self.send_message_to_addr(peer.address, topic, body)

    def stop(self):
        """Stop all worker threads."""
        self.running = False
        # Wait for queues to be processed
        self.incoming_queue.join()
        self.outgoing_queue.join()

    # RouteTable wrapper methods
    def add_peer(self, addr, public_key, difficulty):
        """Add a peer to the routing table."""
        return self.route_table.update_peer(addr, public_key, difficulty)
        
    def get_closest_peers(self, target_id, count=3):
        """Get the closest peers to the target ID."""
        return self.route_table.get_closest_peers(target_id, count=count)
        
    @property
    def num_buckets(self):
        """Get the number of buckets in the routing table."""
        return self.route_table.num_buckets
        
    def get_bucket_peers(self, bucket_index):
        """Get peers from a specific bucket."""
        return self.route_table.get_bucket_peers(bucket_index)
        
    def has_peer(self, addr):
        """Check if a peer with the given address exists in the routing table."""
        return self.route_table.has_peer(addr)
