import os
import hashlib
import time
from typing import Tuple, Optional
import json

from .relay import Relay, Topic
from .relay.peer import Peer
from .models import Storage, Block, Transaction
from .machine import AstreumMachine
from .utils import encode, decode
from astreum.lispeum.storage import store_expr, get_expr_from_storage

class Node:
    def __init__(self, config: dict):
        self.config = config
        self.relay = Relay(config)
        # Get the node_id from relay instead of generating our own
        self.node_id = self.relay.node_id
        self.storage = Storage(config)
        self.storage.node = self  # Set the storage node reference to self
        
        # Latest block of the chain this node is following
        self.latest_block = None
        self.followed_chain_id = config.get('followed_chain_id', None)
        
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
            # Check if we're in the validation route
            # This is now already checked by the relay's _handle_message method
            if not self.relay.is_in_validation_route():
                return
            
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
            
            # Get our current latest block
            our_latest = self.latest_block
            
            # Verify block hash links to our latest block
            if our_latest and block.previous_hash == our_latest.hash:
                # Process the valid block
                self.machine.process_block(block)
                
                # Update our latest block
                self.latest_block = block
            # Check if this block is ahead of our current chain
            elif our_latest and block.height > our_latest.height:
                # Block is ahead but doesn't link directly to our latest
                # Add to candidate chains for potential future adoption
                self._add_candidate_chain(block)
            
            # No automatic broadcasting - nodes will request latest blocks when needed
        except Exception as e:
            print(f"Error handling latest block: {e}")
    
    def _handle_transaction(self, body: bytes, addr: Tuple[str, int], envelope):
        """
        Handle receipt of a transaction.
        Accept if validation route is present and counter is valid relative to the latest block in our chain.
        """
        try:
            # Check if we're in the validation route
            # This is now already checked by the relay's _handle_message method
            if not self.relay.is_in_validation_route():
                return
            
            # Deserialize the transaction
            transaction = Transaction.from_bytes(body)
            if not transaction:
                return
                
            # Check if we're following this chain
            if not self.machine.is_following_chain(transaction.chain_id):
                return
                
            # Verify transaction has a valid validation route
            if not transaction.has_valid_route():
                return
                
            # Get latest block from this chain
            latest_block = self.machine.get_latest_block(transaction.chain_id)
            if not latest_block:
                return
                
            # Verify transaction counter is valid relative to the latest block
            if not transaction.is_counter_valid(latest_block):
                return
                
            # Process the valid transaction
            self.machine.process_transaction(transaction)
            
            # Relay to other peers in the validation route
            validation_peers = self.relay.get_route_peers(1)  # 1 = validation route
            for peer in validation_peers:
                if peer.address != addr:  # Don't send back to originator
                    self.relay.send_message(body, Topic.TRANSACTION, peer.address)
        except Exception as e:
            print(f"Error handling transaction: {e}")
            
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
        Add a block to candidate chains for potential future adoption.
        
        Args:
            block: The block to add as a candidate
        """
        chain_id = block.chain_id
        
        # If we already have this chain as a candidate, only update if this block is newer
        if chain_id in self.candidate_chains:
            current_candidate = self.candidate_chains[chain_id]['latest_block']
            if block.height > current_candidate.height:
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
        
        # Prune old candidates (older than 1 hour)
        self._prune_candidate_chains()
        
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