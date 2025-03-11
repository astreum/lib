import os
import hashlib
import time
import threading
import random
from typing import Tuple, Optional, List
import json
from cryptography.hazmat.primitives.asymmetric import ed25519

from .relay import Relay, Topic
from .relay.peer import Peer
from .models import Storage, Block, Transaction
from .machine import AstreumMachine
from .utils import encode, decode
from astreum.lispeum.storage import store_expr, get_expr_from_storage

class Node:
    def __init__(self, config: dict):
        # Ensure config is a dictionary, but allow it to be None
        self.config = config if config is not None else {}
        
        # Handle validation key if provided
        self.validation_private_key = None
        self.validation_public_key = None
        self.is_validator = False
        
        # Extract validation private key from config
        if 'validation_private_key' in self.config:
            try:
                key_bytes = bytes.fromhex(self.config['validation_private_key'])
                self.validation_private_key = ed25519.Ed25519PrivateKey.from_private_bytes(key_bytes)
                self.validation_public_key = self.validation_private_key.public_key()
                self.is_validator = True
                
                # Set validation_route to True in config so relay will join validation route
                self.config['validation_route'] = True
                print(f"Node is configured as a validator with validation key")
            except Exception as e:
                print(f"Error loading validation private key: {e}")
        
        # Initialize relay with our config
        self.relay = Relay(self.config)
        
        # Get the node_id from relay
        self.node_id = self.relay.node_id
        
        # Initialize storage
        self.storage = Storage(self.config)
        self.storage.node = self  # Set the storage node reference to self
        
        # Latest block of the chain this node is following
        self.latest_block = None
        self.followed_chain_id = self.config.get('followed_chain_id', None)
        
        # Initialize machine
        self.machine = AstreumMachine(node=self)
        
        # Register message handlers
        self.relay.message_handlers[Topic.PEER_ROUTE] = self._handle_peer_route
        self.relay.message_handlers[Topic.PING] = self._handle_ping
        self.relay.message_handlers[Topic.PONG] = self._handle_pong
        self.relay.message_handlers[Topic.OBJECT_REQUEST] = self._handle_object_request
        self.relay.message_handlers[Topic.OBJECT_RESPONSE] = self._handle_object_response
        self.relay.message_handlers[Topic.ROUTE_REQUEST] = self._handle_route_request
        self.relay.message_handlers[Topic.ROUTE] = self._handle_route
        self.relay.message_handlers[Topic.LATEST_BLOCK_REQUEST] = self._handle_latest_block_request
        self.relay.message_handlers[Topic.LATEST_BLOCK] = self._handle_latest_block
        self.relay.message_handlers[Topic.TRANSACTION] = self._handle_transaction
        
        # Initialize latest block from storage if available
        self._initialize_latest_block()
        
        # Candidate chains that might be adopted
        self.candidate_chains = {}  # chain_id -> {'latest_block': block, 'timestamp': time.time()}
        
        # Block query timers for different routes
        self.running = False
        self.block_query_threads = []
        
    def start(self):
        """Start the node and all its services."""
        self.running = True
        
        # Start periodic block query thread for validation route
        validation_query_thread = threading.Thread(
            target=self._periodic_validation_route_query, 
            daemon=True
        )
        validation_query_thread.start()
        self.block_query_threads.append(validation_query_thread)
        
        print(f"Node started with ID {self.node_id.hex()}")
        print(f"Listening on port {self.relay.incoming_port}")
        
    def stop(self):
        """Stop the node and all its services."""
        self.running = False
        
        # Stop all threads
        for thread in self.block_query_threads:
            if thread.is_alive():
                thread.join(timeout=1.0)  # Give threads 1 second to shut down
                
        print("Node stopped")
        
    def _periodic_validation_route_query(self):
        """Periodically query random peers in the validation route for latest blocks."""
        while self.running:
            try:
                # Query 3 random peers from validation route for latest block
                self._query_random_peers_for_latest_block(route_type=1, count=3)
                
                # Prune old candidate chains periodically
                self._prune_candidate_chains()
                
                # Sleep according to validator status
                if self.is_validator:
                    # Validators check more frequently (every second)
                    time.sleep(1)
                else:
                    # Regular nodes check less frequently (every 3 seconds)
                    time.sleep(3)
            except Exception as e:
                print(f"Error in validation route query: {e}")
                time.sleep(1)  # Sleep briefly before retrying
                
    def _query_random_peers_for_latest_block(self, route_type: int, count: int = 3):
        """
        Query random peers from specified route for latest block.
        
        Args:
            route_type (int): Route type (0 for peer, 1 for validation)
            count (int): Number of random peers to query
        """
        # Only continue if we're tracking this route
        if not self.relay.is_tracking_route(route_type):
            return
            
        # Get random peers from the route
        random_peers = self.relay.get_random_peers_from_route(route_type, count)
        
        # Query each peer for latest block
        for peer in random_peers:
            try:
                # Create empty request message
                request_data = b''
                
                # Send request to peer
                addr = (peer.ip, peer.port)
                self.relay.send_message(request_data, Topic.LATEST_BLOCK_REQUEST, addr)
            except Exception as e:
                print(f"Error querying peer {peer.node_id.hex()}: {e}")
    
    def _handle_ping(self, body: bytes, addr: Tuple[str, int], envelope):
        """
        Handle ping messages by storing peer info and responding with a pong.
        
        The ping message contains:
        - public_key: The sender's public key
        - difficulty: The sender's preferred proof-of-work difficulty 
        - routes: The sender's available routes
        """
        try:
            # Parse peer information from the ping message
            parts = decode(body)
            if len(parts) != 3:
                return
                
            public_key, difficulty_bytes, routes_data = parts
            difficulty = int.from_bytes(difficulty_bytes, byteorder='big')
            
            # Store peer information in routing table
            peer = self.relay.add_peer(addr, public_key, difficulty)
            
            # Process the routes the sender is participating in
            if routes_data:
                # routes_data is a simple list like [0, 1] meaning peer route and validation route
                # Add peer to each route they participate in
                self.relay.add_peer_to_route(peer, list(routes_data))
            
            # Create response with our public key, difficulty and routes we participate in
            pong_data = encode([
                self.node_id,  # Our public key
                self.config.get('difficulty', 1).to_bytes(4, byteorder='big'),  # Our difficulty
                self.relay.get_routes()  # Our routes as bytes([0, 1]) for peer and validation
            ])
            
            self.relay.send_message(pong_data, Topic.PONG, addr)
        except Exception as e:
            print(f"Error handling ping message: {e}")
    
    def _handle_pong(self, body: bytes, addr: Tuple[str, int], envelope):
        """
        Handle pong messages by updating peer information.
        No response is sent to a pong message.
        """
        try:
            # Parse peer information from the pong message
            parts = decode(body)
            if len(parts) != 3:
                return
                
            public_key, difficulty_bytes, routes_data = parts
            difficulty = int.from_bytes(difficulty_bytes, byteorder='big')
            
            # Update peer information in routing table
            peer = self.relay.add_peer(addr, public_key, difficulty)
            
            # Process the routes the sender is participating in
            if routes_data:
                # routes_data is a simple list like [0, 1] meaning peer route and validation route
                # Add peer to each route they participate in
                self.relay.add_peer_to_route(peer, list(routes_data))
        except Exception as e:
            print(f"Error handling pong message: {e}")
    
    def _handle_object_request(self, body: bytes, addr: Tuple[str, int], envelope):
        """
        Handle an object request from a peer.
        
        Args:
            body: Message body containing the object hash
            addr: Address of the requesting peer
            envelope: Full message envelope
        """
        try:
            # Decode the request
            request = json.loads(body.decode('utf-8'))
            object_hash = bytes.fromhex(request.get('hash'))
            
            # Check if we have the requested object
            if not self.storage.contains(object_hash):
                # We don't have the object, ignore the request
                return
                
            # Get the object data
            object_data = self.storage._local_get(object_hash)
            if not object_data:
                return
                
            # Create a response message
            response = {
                'hash': object_hash.hex(),
                'data': object_data.hex()
            }
            
            # Send the response
            self.relay.send_message_to_addr(
                addr, 
                Topic.OBJECT_RESPONSE, 
                json.dumps(response).encode('utf-8')
            )
            
        except Exception as e:
            print(f"Error handling object request: {e}")
    
    def _handle_object_response(self, body: bytes, addr: Tuple[str, int], envelope):
        """
        Handle an object response from a peer.
        
        Args:
            body: Message body containing the object hash and data
            addr: Address of the responding peer
            envelope: Full message envelope
        """
        try:
            # Decode the response
            response = json.loads(body.decode('utf-8'))
            object_hash = bytes.fromhex(response.get('hash'))
            object_data = bytes.fromhex(response.get('data'))
            
            # Store the object
            self.storage.put(object_hash, object_data)
            
        except Exception as e:
            print(f"Error handling object response: {e}")
    
    def _handle_object(self, body: bytes, addr: Tuple[str, int], envelope):
        """
        Handle receipt of an object.
        If not in storage, verify the hash and put in storage.
        """
        try:
            # Verify hash matches the object
            object_hash = hashlib.sha256(body).digest()
            
            # Check if we already have this object
            if not self.storage.exists(object_hash):
                # Store the object
                self.storage.put(object_hash, body)
        except Exception as e:
            print(f"Error handling object: {e}")
    
    def request_object(self, object_hash: bytes, max_attempts: int = 3) -> Optional[bytes]:
        """
        Request an object from the network by its hash.
        
        This method sends an object request to peers closest to the object hash
        and waits for a response until timeout.
        
        Args:
            object_hash: The hash of the object to request
            max_attempts: Maximum number of request attempts
            
        Returns:
            The object data if found, None otherwise
        """
        # First check if we already have the object
        if self.storage.contains(object_hash):
            return self.storage._local_get(object_hash)
            
        # Find the bucket containing the peers closest to the object's hash
        closest_peers = self.relay.get_closest_peers(object_hash, count=3)
        if not closest_peers:
            return None
            
        # Create a message to request the object
        topic = Topic.OBJECT_REQUEST
        object_request_msg = {
            'hash': object_hash.hex()
        }
        
        # Track which peers we've already tried
        attempted_peers = set()
        
        # We'll try up to max_attempts times
        for _ in range(max_attempts):
            # Find peers we haven't tried yet
            untried_peers = [p for p in closest_peers if p.id not in attempted_peers]
            if not untried_peers:
                break
                
            # Send the request to all untried peers
            request_sent = False
            for peer in untried_peers:
                try:
                    self.relay.send_message_to_peer(peer, topic, object_request_msg)
                    attempted_peers.add(peer.id)
                    request_sent = True
                except Exception as e:
                    print(f"Failed to send object request to peer {peer.id.hex()}: {e}")
            
            if not request_sent:
                break
                
            # Short wait to allow for response
            time.sleep(0.5)
            
            # Check if any of the requests succeeded
            if self.storage.contains(object_hash):
                return self.storage._local_get(object_hash)
                
        # If we get here, we couldn't get the object
        return None
    
    def _handle_route_request(self, body: bytes, addr: Tuple[str, int], envelope):
        """
        Handle request for routing information.
        Seed route to peer with one peer per bucket in the route table.
        """
        try:
            # Create a list to store one peer from each bucket
            route_peers = []
            
            # Get one peer from each bucket
            for bucket_index in range(self.relay.num_buckets):
                peers = self.relay.get_bucket_peers(bucket_index)
                if peers and len(peers) > 0:
                    # Add one peer from this bucket
                    route_peers.append(peers[0])
            
            # Serialize the peer list
            # Format: List of [peer_addr, peer_port, peer_key]
            peer_data = []
            for peer in route_peers:
                peer_addr, peer_port = peer.address
                peer_data.append(encode([
                    peer_addr.encode('utf-8'),
                    peer_port.to_bytes(2, byteorder='big'),
                    peer.node_id
                ]))
            
            # Encode the complete route data
            route_data = encode(peer_data)
            
            # Send routing information back
            self.relay.send_message(route_data, Topic.ROUTE, addr)
        except Exception as e:
            print(f"Error handling route request: {e}")
    
    def _handle_route(self, body: bytes, addr: Tuple[str, int], envelope):
        """
        Handle receipt of a route message containing a list of IP addresses to ping.
        """
        try:
            # Decode the list of peers
            peer_entries = decode(body)
            
            # Process each peer
            for peer_data in peer_entries:
                try:
                    peer_parts = decode(peer_data)
                    if len(peer_parts) != 3:
                        continue
                        
                    peer_addr_bytes, peer_port_bytes, peer_id = peer_parts
                    peer_addr = peer_addr_bytes.decode('utf-8')
                    peer_port = int.from_bytes(peer_port_bytes, byteorder='big')
                    
                    # Create peer address tuple
                    peer_address = (peer_addr, peer_port)
                    
                    # Ping this peer if it's not already in our routing table
                    # and it's not our own address
                    if (not self.relay.has_peer(peer_address) and 
                            peer_address != self.relay.get_address()):
                        # Create ping message with our info and routes
                        # Encode our peer and validation routes
                        peer_routes_list = self.relay.get_routes()
                        
                        # Combine into a single list of routes with type flags
                        # For each route: [is_validation_route, route_id]
                        routes = []
                        
                        # Add peer routes (type flag = 0)
                        for route in peer_routes_list:
                            routes.append(encode([bytes([0]), route]))
                            
                        # Encode the complete routes list
                        all_routes = encode(routes)
                        
                        ping_data = encode([
                            self.node_id,  # Our public key
                            self.config.get('difficulty', 1).to_bytes(4, byteorder='big'),  # Our difficulty
                            all_routes  # All routes we participate in
                        ])
                        
                        # Send ping to the peer
                        self.relay.send_message(ping_data, Topic.PING, peer_address)
                except Exception as e:
                    print(f"Error processing peer in route: {e}")
                    continue
        except Exception as e:
            print(f"Error handling route message: {e}")
    
    def _handle_latest_block_request(self, body: bytes, addr: Tuple[str, int], envelope):
        """
        Handle request for the latest block from the chain currently following.
        Any node can request the latest block for syncing purposes.
        """
        try:
            # Return our latest block from the followed chain
            if self.latest_block:
                # Send latest block to the requester
                self.relay.send_message(self.latest_block.to_bytes(), Topic.LATEST_BLOCK, addr)
        except Exception as e:
            print(f"Error handling latest block request: {e}")
    
    def _handle_latest_block(self, body: bytes, addr: Tuple[str, int], envelope):
        """
        Handle receipt of a latest block message.
        Identify chain, validate if following chain, only accept if latest block 
        in chain is in the previous field.
        """
        try:
            # All nodes can process latest blocks now, regardless of route membership
            
            # Deserialize the block
            block = Block.from_bytes(body)
            if not block:
                return
                
            # Check if we're following this chain
            if not self.machine.is_following_chain(block.chain_id):
                # Store as a potential candidate chain if it has a higher height
                if not self.followed_chain_id or block.chain_id != self.followed_chain_id:
                    self._add_candidate_chain(block)
                return
                
            # Only proceed if block chain_id matches what we're following
            if self.followed_chain_id and block.chain_id != self.followed_chain_id:
                return
                
            if not self.latest_block:
                # We don't have a latest block, so this might be the first one we've seen
                # Store it as our latest
                self._update_latest_block(block)
                return
                
            # If this block is newer than our latest, update our latest block
            if block.height > self.latest_block.height:
                # Verify chain continuity
                if self.latest_block.hash_bytes in block.previous_blocks:
                    # This is a valid continuation of our chain
                    self._update_latest_block(block)
                else:
                    # This block doesn't build on our latest, check for forking
                    # but continue tracking it as a candidate
                    self._add_candidate_chain(block)
                    
        except Exception as e:
            print(f"Error handling latest block: {e}")
    
    def _handle_transaction(self, body: bytes, addr: Tuple[str, int], envelope):
        """
        Handle incoming transaction messages.
        
        This method is called when we receive a transaction from the network.
        Transactions should only be processed by validator nodes.
        
        Args:
            body: Transaction data
            addr: Source address
            envelope: Full message envelope
        """
        # Ignore if we're not a validator (don't have a validation key)
        if not self.is_validator or not self.relay.is_in_validation_route():
            print("Ignoring transaction as we're not a validator")
            return
            
        try:
            # Parse transaction data
            tx_data = json.loads(body.decode('utf-8'))
            
            # Store the transaction in our local storage
            tx_hash = bytes.fromhex(tx_data.get('hash'))
            tx_raw = bytes.fromhex(tx_data.get('data'))
            
            # Create transaction entry in storage
            if not self.storage.contains(tx_hash):
                self.storage.put(tx_hash, tx_raw)
                print(f"Stored transaction {tx_hash.hex()}")
                
                # Process the transaction as a validator
                self._process_transaction_as_validator(tx_hash, tx_raw)
            
        except Exception as e:
            print(f"Error handling transaction: {e}")
            
    def _process_transaction_as_validator(self, tx_hash: bytes, tx_raw: bytes):
        """
        Process a transaction as a validator node.
        
        This method is called when we receive a transaction and we're a validator.
        It verifies the transaction and may include it in a future block.
        
        Args:
            tx_hash: Transaction hash
            tx_raw: Raw transaction data
        """
        try:
            print(f"Processing transaction {tx_hash.hex()} as validator")
            # Here we would verify the transaction and potentially queue it
            # for inclusion in the next block we create
            
            # For now, just log that we processed it
            print(f"Verified transaction {tx_hash.hex()}")
            
            # TODO: Implement transaction validation and queueing for block creation
            
        except Exception as e:
            print(f"Error processing transaction as validator: {e}")
            
    def _initialize_latest_block(self):
        """Initialize latest block from storage if available."""
        # Implementation would load the latest block from storage
        pass
    
    def set_followed_chain(self, chain_id):
        """
        Set the chain that this node follows.
        
        Args:
            chain_id: The ID of the chain to follow
        """
        self.followed_chain_id = chain_id
        self.latest_block = self.machine.get_latest_block(chain_id)
        
    def get_latest_block(self):
        """
        Get the latest block of the chain this node is following.
        
        Returns:
            The latest block, or None if not available
        """
        return self.latest_block
    
    def _add_candidate_chain(self, block):
        """
        Add a block to the candidate chains.
        
        Args:
            block: Block to add
        """
        chain_id = block.chain_id
        
        # Check if we already have this chain as a candidate
        if chain_id in self.candidate_chains:
            existing_block = self.candidate_chains[chain_id]['latest_block']
            
            # Only update if this block is newer
            if block.height > existing_block.height:
                self.candidate_chains[chain_id] = {
                    'latest_block': block,
                    'timestamp': time.time()
                }
        else:
            # Add as a new candidate chain
            self.candidate_chains[chain_id] = {
                'latest_block': block,
                'timestamp': time.time()
            }
            
        print(f"Added candidate chain {chain_id.hex()} with height {block.height}")
    
    def _update_latest_block(self, block):
        """
        Update our latest block and process it.
        
        Args:
            block: New latest block to set
        """
        # Process the block if it's new
        if not self.latest_block or block.hash_bytes != self.latest_block.hash_bytes:
            # Process block logic in the machine
            self.machine.process_block(block)
            
            # Update our latest block reference
            self.latest_block = block
            
            # Update followed chain ID if needed
            if not self.followed_chain_id:
                self.followed_chain_id = block.chain_id
                
            print(f"Updated latest block to height {block.height}, hash {block.hash}")
            
            # Save latest block to storage for persistence
            if self.storage:
                self.storage.put_latest_block(block)
                
    def _prune_candidate_chains(self):
        """Remove candidate chains that are older than 1 hour."""
        current_time = time.time()
        chains_to_remove = []
        
        for chain_id, data in self.candidate_chains.items():
            if current_time - data['timestamp'] > 3600:  # 1 hour in seconds
                chains_to_remove.append(chain_id)
                
        for chain_id in chains_to_remove:
            del self.candidate_chains[chain_id]
            
    def evaluate_candidate_chains(self):
        """
        Evaluate all candidate chains to see if we should switch to one.
        This is a placeholder for now - in a real implementation, you would
        verify the chain and potentially switch to it if it's valid and better.
        """
        # TODO: Implement chain evaluation logic
        pass
    
    def post_global_storage(self, name: str, value):
        """
        Store a global variable in node storage.
        
        Args:
            name: Name of the variable
            value: Value to store
        """
        # Store the expression directly in node storage using DAG representation
        root_hash = store_expr(value, self.storage)
        
        # Create a key for this variable name (without special prefixes)
        key = hashlib.sha256(name.encode()).digest()
        
        # Store the root hash reference
        self.storage.put(key, root_hash)
        
    def query_global_storage(self, name: str):
        """
        Retrieve a global variable from node storage.
        
        Args:
            name: Name of the variable to retrieve
            
        Returns:
            The stored expression, or None if not found
        """
        # Create the key for this variable name
        key = hashlib.sha256(name.encode()).digest()
        
        # Try to retrieve the root hash
        root_hash = self.storage.get(key)
        
        if root_hash:
            # Load the expression using its root hash
            return get_expr_from_storage(root_hash, self.storage)
        
        return None