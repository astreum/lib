import time
import threading
from typing import List
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from .relay import Relay, Topic
from ..machine import AstreumMachine
from .utils import hash_data
from .validation.block import Block
from .storage.storage import Storage

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
        
        # Initialize blockchain state
        self.blockchain = create_account_state(self.config)
        
        # Store our validator info if we're a validator
        if self.is_validator and self.validation_public_key:
            self.validator_address = self.validation_public_key.public_bytes(
                encoding=serialization.Encoding.Raw, 
                format=serialization.PublicFormat.Raw
            )
            self.validator_private_bytes = self.validation_private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
            print(f"Registered validator with address: {self.validator_address.hex()}")
        else:
            self.validator_address = None
            self.validator_private_bytes = None
        
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
        self.relay.message_handlers[Topic.BLOCK_REQUEST] = self._handle_block_request
        self.relay.message_handlers[Topic.BLOCK_RESPONSE] = self._handle_block_response
        
        # Initialize latest block from storage if available
        self._initialize_latest_block()
        
        # Candidate chains that might be adopted
        self.candidate_chains = {}  # chain_id -> {'latest_block': block, 'timestamp': time.time()}
        self.pending_blocks = {}  # block_hash -> {'block': block, 'timestamp': time.time()}
        
        # Threads for validation and chain monitoring
        self.running = False
        self.main_chain_validation_thread = None
        self.candidate_chain_validation_thread = None
        
        # Pending transactions for a block
        self.pending_transactions = {}  # tx_hash -> {'transaction': tx, 'timestamp': time.time()}
        
        # Last block production attempt time
        self.last_block_attempt_time = 0

    def start(self):
        """Start the node."""
        self.running = True
        
        # Start relay
        self.relay.start()
        
        # Start chain monitoring thread
        self.main_chain_validation_thread = threading.Thread(
            target=self._main_chain_validation_loop,
            name="MainChainValidation"
        )
        self.main_chain_validation_thread.daemon = True
        self.main_chain_validation_thread.start()
        
        self.candidate_chain_validation_thread = threading.Thread(
            target=self._candidate_chain_validation_loop,
            name="CandidateChainValidation"
        )
        self.candidate_chain_validation_thread.daemon = True
        self.candidate_chain_validation_thread.start()
        
        # Set up recurring block query tasks
        main_query_thread = threading.Thread(
            target=self._block_query_loop,
            args=('main',),
            daemon=True
        )
        main_query_thread.start()
        
        validation_query_thread = threading.Thread(
            target=self._block_query_loop,
            args=('validation',),
            daemon=True
        )
        validation_query_thread.start()
        
        print(f"Node started with ID {self.node_id.hex()}")

    def stop(self):
        """Stop the node and all its services."""
        self.running = False
        
        # Stop all threads
        if self.main_chain_validation_thread and self.main_chain_validation_thread.is_alive():
            self.main_chain_validation_thread.join(timeout=1.0)
            
        if self.candidate_chain_validation_thread and self.candidate_chain_validation_thread.is_alive():
            self.candidate_chain_validation_thread.join(timeout=1.0)
            
        # Stop relay last
        if self.relay:
            self.relay.stop()
            
        print("Node stopped")
    
    def _main_chain_validation_loop(self):
        """
        Main validation loop for the primary blockchain.
        This thread prioritizes validating blocks on the main chain we're following.
        """
        while self.running:
            try:
                # Update latest block if we don't have one yet
                if not self.latest_block and hasattr(self.blockchain, 'get_latest_block'):
                    self.latest_block = self.blockchain.get_latest_block()
                
                # Process any blocks that extend our main chain immediately
                self._process_main_chain_blocks()
                
                # Attempt block production if we are a validator
                if self.is_validator and self.validator_address:
                    self._attempt_block_production()
                
                # Cleanup old items
                self._prune_pending_items()
                
                # Sleep to prevent high CPU usage
                time.sleep(0.1)  # Short sleep for main chain validation
            except Exception as e:
                print(f"Error in main chain validation loop: {e}")
                time.sleep(1)  # Longer sleep on error
                
    def _candidate_chain_validation_loop(self):
        """
        Validation loop for candidate chains (potential forks).
        This thread handles validation of blocks from alternate chains 
        without slowing down the main chain processing.
        """
        while self.running:
            try:
                # Process candidate chains
                self._evaluate_candidate_chains()
                
                # Prune old candidate chains
                self._prune_candidate_chains()
                
                # Sleep longer for candidate chain validation (lower priority)
                time.sleep(1)  # Longer sleep for candidate chain validation
            except Exception as e:
                print(f"Error in candidate chain validation loop: {e}")
                time.sleep(2)  # Even longer sleep on error
                
    def _prune_pending_items(self):
        """Remove old pending blocks and transactions."""
        current_time = time.time()
        
        # Prune old pending blocks (older than 1 hour)
        blocks_to_remove = [
            block_hash for block_hash, data in self.pending_blocks.items()
            if current_time - data['timestamp'] > 3600  # 1 hour
        ]
        for block_hash in blocks_to_remove:
            del self.pending_blocks[block_hash]
            
        # Prune old pending transactions (older than 30 minutes)
        txs_to_remove = [
            tx_hash for tx_hash, data in self.pending_transactions.items()
            if current_time - data['timestamp'] > 1800  # 30 minutes
        ]
        for tx_hash in txs_to_remove:
            del self.pending_transactions[tx_hash]
            
    def _process_main_chain_blocks(self):
        """
        Process blocks that extend our current main chain.
        Prioritizes blocks that build on our latest block.
        """
        # Skip if we don't have a latest block yet
        if not self.latest_block:
            return
            
        # Get the hash of our latest block
        latest_hash = self.latest_block.get_hash()
        
        # Find any pending blocks that build on our latest block
        main_chain_blocks = []
        for block_hash, data in list(self.pending_blocks.items()):
            block = data['block']
            
            # Check if this block extends our latest block
            if block.previous == latest_hash:
                main_chain_blocks.append(block)
                
        # Process found blocks
        for block in main_chain_blocks:
            self._validate_and_process_main_chain_block(block)
            
    def _validate_and_process_main_chain_block(self, block: Block):
        """
        Validate and process a block that extends our main chain.
        
        Args:
            block: Block to validate and process
        """
        try:
            # Validate block
            is_valid = validate_block(block, self.blockchain.get_accounts_at_block(block.previous), self.blockchain.get_blocks())
            
            if is_valid:
                # Apply block to our state
                success = validate_and_apply_block(self.blockchain, block)
                if success:
                    print(f"Applied valid block {block.number} to blockchain state")
                    self._update_latest_block(block)
                    blocks_to_remove = [block.get_hash()]
                    for block_hash in blocks_to_remove:
                        if block_hash in self.pending_blocks:
                            del self.pending_blocks[block_hash]
                    print(f"Added block {block.number} to blockchain")
                    return True
        except Exception as e:
            print(f"Error validating main chain block {block.number}: {e}")
            
        return False
            
    def _evaluate_candidate_chains(self):
        """
        Evaluate candidate chains to determine if any should become our main chain.
        This will validate pending blocks and look for chains with higher cumulative difficulty.
        """
        # Skip if no candidate chains
        if not self.candidate_chains:
            return
            
        # For each candidate chain, validate blocks and calculate metrics
        for chain_id, data in list(self.candidate_chains.items()):
            latest_candidate_block = data['latest_block']
            
            # Build the chain backwards
            chain_blocks = self._build_chain_from_latest(latest_candidate_block)
            
            # Skip if we couldn't build a complete chain
            if not chain_blocks:
                continue
                
            # Validate the entire chain
            valid_chain = self._validate_candidate_chain(chain_blocks)
            
            # If valid and better than our current chain, switch to it
            if valid_chain and self._is_better_chain(chain_blocks):
                self._switch_to_new_chain(chain_blocks)
                
    def _build_chain_from_latest(self, latest_block: Block) -> List[Block]:
        """
        Build a chain from the latest block back to a known point in our blockchain.
        
        Args:
            latest_block: Latest block in the candidate chain
            
        Returns:
            List of blocks in the chain, ordered from oldest to newest
        """
        chain_blocks = [latest_block]
        current_block = latest_block
        
        # Track visited blocks to avoid cycles
        visited = {current_block.get_hash()}
        
        # Build chain backwards until we either:
        # 1. Find a block in our main chain
        # 2. Run out of blocks
        # 3. Detect a cycle
        while current_block.number > 0:
            previous_hash = current_block.previous
            
            # Check if we have this block in our blockchain
            if hasattr(self.blockchain, 'has_block') and self.blockchain.has_block(previous_hash):
                # Found connection to our main chain
                previous_block = self.blockchain.get_block(previous_hash)
                chain_blocks.insert(0, previous_block)
                break
                
            # Check if block is in pending blocks
            elif previous_hash in self.pending_blocks:
                previous_block = self.pending_blocks[previous_hash]['block']
                
                # Check for cycles
                if previous_hash in visited:
                    print(f"Cycle detected in candidate chain at block {previous_block.number}")
                    return []
                    
                visited.add(previous_hash)
                chain_blocks.insert(0, previous_block)
                current_block = previous_block
            else:
                # Missing block, cannot validate the chain
                print(f"Missing block {previous_hash.hex()} in candidate chain")
                return []
                
        return chain_blocks
        
    def _validate_candidate_chain(self, chain_blocks: List[Block]) -> bool:
        """
        Validate a candidate chain of blocks.
        
        Args:
            chain_blocks: List of blocks in the chain (oldest to newest)
            
        Returns:
            True if the chain is valid, False otherwise
        """
        # Validate each block in the chain
        for i, block in enumerate(chain_blocks):
            # Skip first block, it's either genesis or a block we already have
            if i == 0:
                continue
                
            # Validate block connections
            if block.previous != chain_blocks[i-1].get_hash():
                print(f"Invalid chain: block {block.number} does not reference previous block")
                return False
                
            # Validate block
            is_valid = validate_block(block, self.blockchain.get_accounts_at_block(block.previous), self.blockchain.get_blocks())
            if not is_valid:
                print(f"Invalid chain: block {block.number} is invalid")
                return False
                
        return True
        
    def _is_better_chain(self, chain_blocks: List[Block]) -> bool:
        """
        Determine if a candidate chain is better than our current chain.
        
        Args:
            chain_blocks: List of blocks in the candidate chain
            
        Returns:
            True if the candidate chain is better, False otherwise
        """
        # Get the latest block from the candidate chain
        candidate_latest = chain_blocks[-1]
        
        # If we don't have a latest block, any valid chain is better
        if not self.latest_block:
            return True
            
        # Compare block numbers (longest chain rule)
        if candidate_latest.number > self.latest_block.number:
            print(f"Candidate chain is longer: {candidate_latest.number} vs {self.latest_block.number}")
            return True
            
        return False
        
    def _switch_to_new_chain(self, chain_blocks: List[Block]):
        """
        Switch to a new chain by adding all blocks to our blockchain.
        
        Args:
            chain_blocks: List of blocks in the chain (oldest to newest)
        """
        # Find the point where the chains diverge
        divergence_point = 0
        for i, block in enumerate(chain_blocks):
            # Check if we have this block in our blockchain
            if hasattr(self.blockchain, 'has_block') and self.blockchain.has_block(block.get_hash()):
                divergence_point = i + 1
            else:
                break
                
        # Add all blocks after the divergence point
        for i in range(divergence_point, len(chain_blocks)):
            block = chain_blocks[i]
            
            # Add block to blockchain
            if hasattr(self.blockchain, 'add_block'):
                try:
                    self.blockchain.add_block(block)
                    
                    # Remove from pending blocks
                    block_hash = block.get_hash()
                    if block_hash in self.pending_blocks:
                        del self.pending_blocks[block_hash]
                        
                    print(f"Added block {block.number} to blockchain")
                except Exception as e:
                    print(f"Error adding block {block.number} to blockchain: {e}")
                    return
                    
        # Update latest block
        self._update_latest_block(chain_blocks[-1])
        print(f"Switched to new chain, latest block: {self.latest_block.number}")