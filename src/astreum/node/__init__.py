class Node:
    def __init__(self, config: dict):
        self.config = config
        self.node_id = config.get('node_id', os.urandom(32))  # Default to random ID if not provided
        self.relay = Relay(config)
        self.storage = Storage(config)
        self.machine = AstreumMachine(config)
        self.route_table = RouteTable(config, self.node_id)
        
        # Register message handlers
        self._register_message_handlers()
        
    def _register_message_handlers(self):
        """Register handlers for different message topics."""
        self.relay.register_message_handler(Topic.PING, self._handle_ping)
        self.relay.register_message_handler(Topic.PONG, self._handle_pong)
        self.relay.register_message_handler(Topic.OBJECT_REQUEST, self._handle_object_request)
        self.relay.register_message_handler(Topic.OBJECT, self._handle_object)
        self.relay.register_message_handler(Topic.ROUTE_REQUEST, self._handle_route_request)
        self.relay.register_message_handler(Topic.ROUTE, self._handle_route)
        self.relay.register_message_handler(Topic.LATEST_BLOCK_REQUEST, self._handle_latest_block_request)
        self.relay.register_message_handler(Topic.LATEST_BLOCK, self._handle_latest_block)
        self.relay.register_message_handler(Topic.TRANSACTION, self._handle_transaction)
        
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
            self.route_table.update_peer(addr, public_key, difficulty)
            
            # Respond with a pong message
            # Include our public key, difficulty and routes in response
            pong_data = encode([
                self.node_id,  # Our public key
                self.config.get('difficulty', 1).to_bytes(4, byteorder='big'),  # Our difficulty
                b''  # Our routes (placeholder)
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
            self.route_table.update_peer(addr, public_key, difficulty)
        except Exception as e:
            print(f"Error handling pong message: {e}")
    
    def _handle_object_request(self, body: bytes, addr: Tuple[str, int], envelope):
        """
        Handle request for an object by its hash.
        Check storage and return if available, otherwise ignore.
        """
        try:
            # The body is the hash of the requested object
            object_hash = body
            object_data = self.storage.get(object_hash)
            
            if object_data:
                # Object found, send it back
                self.relay.send_message(object_data, Topic.OBJECT, addr)
            # If object not found, simply ignore the request
        except Exception as e:
            print(f"Error handling object request: {e}")
    
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
    
    def _handle_route_request(self, body: bytes, addr: Tuple[str, int], envelope):
        """
        Handle request for routing information.
        Seed route to peer with one peer per bucket in the route table.
        """
        try:
            # Create a list to store one peer from each bucket
            route_peers = []
            
            # Get one peer from each bucket
            for bucket_index in range(self.route_table.num_buckets):
                peers = self.route_table.get_bucket_peers(bucket_index)
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
                    if (not self.route_table.has_peer(peer_address) and 
                            peer_address != self.relay.get_address()):
                        # Create ping message with our info
                        ping_data = encode([
                            self.node_id,  # Our public key
                            self.config.get('difficulty', 1).to_bytes(4, byteorder='big'),  # Our difficulty
                            b''  # Our routes (placeholder)
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
        """
        try:
            # Get the latest block from our currently followed chain
            latest_block = self.machine.get_latest_block()
            
            if latest_block:
                # Send the latest block data
                self.relay.send_message(latest_block.to_bytes(), Topic.LATEST_BLOCK, addr)
        except Exception as e:
            print(f"Error handling latest block request: {e}")
    
    def _handle_latest_block(self, body: bytes, addr: Tuple[str, int], envelope):
        """
        Handle receipt of a latest block message.
        Identify chain, validate if following chain, only accept if latest block 
        in chain is in the previous field.
        """
        try:
            # Deserialize the block
            block = Block.from_bytes(body)
            if not block:
                return
                
            # Check if we're following this chain
            if self.machine.is_following_chain(block.chain_id):
                # Get our current latest block
                our_latest = self.machine.get_latest_block(block.chain_id)
                
                if our_latest and block.previous == our_latest.hash:
                    # Valid next block, process it
                    self.machine.process_block(block)
                elif block.height > our_latest.height + 1:
                    # We're behind, request missing blocks
                    # In a real implementation, would implement a sync process here
                    pass
        except Exception as e:
            print(f"Error handling latest block: {e}")
    
    def _handle_transaction(self, body: bytes, addr: Tuple[str, int], envelope):
        """
        Handle receipt of a transaction.
        Accept if validation route is present and counter is valid relative to the latest block in our chain.
        """
        try:
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
        except Exception as e:
            print(f"Error handling transaction: {e}")