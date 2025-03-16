"""
Account validation and stake management for the Astreum blockchain.
"""

import time
import json
from typing import Dict, Optional, Tuple, List, Set, Any
from dataclasses import dataclass, field
from ..utils import hash_data
from ..storage import Storage
from ..storage.merkle import MerkleNode, MerkleTree
from .stake import process_stake_transaction

from .constants import VALIDATION_ADDRESS, MIN_STAKE_AMOUNT


@dataclass
class Account:
    """
    Account class for tracking balance and account state.
    """
    address: bytes
    balance: int = 0
    counter: int = 0
    data: bytes = field(default_factory=lambda: b'')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert account to dictionary representation"""
        return {
            'address': self.address.hex(),
            'balance': self.balance,
            'counter': self.counter,
            'data': self.data.hex() if self.data else ''
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Account':
        """Create account from dictionary representation"""
        return cls(
            address=bytes.fromhex(data['address']),
            balance=data['balance'],
            counter=data['counter'],
            data=bytes.fromhex(data['data']) if data['data'] else b''
        )


def get_account_details(storage: Storage, details_hash: bytes) -> Optional[Account]:
    """
    Retrieve account details from storage using a details hash.
    
    Args:
        storage: Storage instance to retrieve data from
        details_hash: Hash of the account details to retrieve
        
    Returns:
        Account object if found, None otherwise
    """
    # Retrieve the account node from storage
    node_data = storage.get(details_hash)
    if not node_data:
        return None
        
    # Deserialize the node
    node = MerkleNode.deserialize(node_data)
    if not node or not node.data:
        return None
        
    # Try to parse the account data
    try:
        # Assuming the node.data contains a serialized JSON or similar format
        # that can be converted to a dictionary and then to an Account
        import json
        account_dict = json.loads(node.data.decode('utf-8'))
        return Account.from_dict(account_dict)
    except Exception as e:
        print(f"Error parsing account data: {e}")
        return None


def get_validator_stake(accounts: Dict[bytes, Account], validator_address: bytes) -> int:
    """
    Get the stake amount for a specific validator.
    
    Args:
        accounts: Dictionary mapping addresses to Account objects
        validator_address: Address of the validator to check
        
    Returns:
        Stake amount for the validator, or 0 if not a validator
    """
    # This function would need to be updated to use a separate stake lookup
    # For now, returning 0 as a placeholder
    return 0


def is_validator(accounts: Dict[bytes, Account], address: bytes) -> bool:
    """
    Check if an address is registered as a validator.
    
    Args:
        accounts: Dictionary mapping addresses to Account objects
        address: Address to check
        
    Returns:
        True if the address is a validator, False otherwise
    """
    # This function would need to be updated to use a separate stake lookup
    # For now, returning False as a placeholder
    return False


def create_genesis_account(address: bytes, balance: int = 1000) -> Account:
    """
    Create a genesis account with initial balance.
    
    Args:
        address: Address of the genesis account
        balance: Initial balance (default: 1000)
        
    Returns:
        New Account object
    """
    return Account(
        address=address,
        balance=balance,
        counter=0,
        data=b''
    )


def apply_transaction_to_account(
    accounts: Dict[bytes, Account], 
    sender: bytes, 
    recipient: bytes, 
    amount: int, 
    data: bytes = b'',
    storage: Optional[Storage] = None,
    stake_root: Optional[bytes] = None
) -> Tuple[bool, Optional[bytes]]:
    """
    Apply a transaction to update account balances.
    
    Args:
        accounts: Dictionary mapping addresses to Account objects
        sender: Sender address
        recipient: Recipient address
        amount: Amount to transfer
        data: Transaction data
        storage: Storage instance (required for staking transactions)
        stake_root: Root hash of the stake Merkle tree (required for staking transactions)
        
    Returns:
        Tuple containing:
        - Boolean indicating if transaction was successfully applied
        - New stake root hash if transaction was a staking transaction, otherwise None
    """
    # Ensure accounts exist
    if sender not in accounts:
        return False, None
    
    # Get sender account
    sender_account = accounts[sender]
    
    # Check if sender has sufficient balance
    if sender_account.balance < amount:
        return False, None
    
    # Handle special case for staking (sending to validation address)
    if recipient == VALIDATION_ADDRESS:
        # This is a staking transaction
        if not storage or stake_root is None:
            # Cannot process staking without storage and stake root
            return False, None
            
        # Update account balance
        sender_account.balance -= amount
        sender_account.counter += 1
        
        # Update stake in the Merkle tree
        new_stake_root = process_stake_transaction(
            storage,
            stake_root,
            sender,
            amount
        )
        
        return True, new_stake_root
    
    # Create recipient account if it doesn't exist
    if recipient not in accounts:
        accounts[recipient] = Account(address=recipient)
    
    # Get recipient account
    recipient_account = accounts[recipient]
    
    # Handle regular transaction
    sender_account.balance -= amount
    recipient_account.balance += amount
    sender_account.counter += 1
    
    # Update data if provided
    if data:
        recipient_account.data = data
    
    return True, None


def store_account(storage: Storage, account: Account) -> bytes:
    """
    Stores an account in the hierarchical Merkle tree structure and returns the account hash.
    
    Structure:
    - Account tree
      - Address tree (addresses as leaves)
      - Details tree
        - Balance
        - Code
        - Counter
        - Storage
        
    Args:
        storage: Storage instance
        account: Account to store
        
    Returns:
        Root hash of the account tree
    """
    from ..storage.merkle import MerkleTree
    import json
    
    # First, build the detail leaves
    detail_leaves = []
    
    # Balance leaf
    balance_data = {'type': 'balance', 'value': account.balance}
    balance_leaf = json.dumps(balance_data).encode('utf-8')
    detail_leaves.append(balance_leaf)
    
    # Code/data leaf (account data)
    code_data = {'type': 'code', 'value': account.data.hex() if account.data else ''}
    code_leaf = json.dumps(code_data).encode('utf-8')
    detail_leaves.append(code_leaf)
    
    # Counter leaf
    counter_data = {'type': 'counter', 'value': account.counter}
    counter_leaf = json.dumps(counter_data).encode('utf-8')
    detail_leaves.append(counter_leaf)
    
    # Storage leaf (placeholder for now)
    storage_data = {'type': 'storage', 'value': ''}
    storage_leaf = json.dumps(storage_data).encode('utf-8')
    detail_leaves.append(storage_leaf)
    
    # Build the details Merkle tree
    details_tree = MerkleTree(storage)
    details_root = details_tree.add(detail_leaves)
    
    # Create address and details nodes
    address_data = {'type': 'address', 'value': account.address.hex()}
    address_leaf = json.dumps(address_data).encode('utf-8')
    
    details_data = {'type': 'details', 'root': details_root.hex()}
    details_leaf = json.dumps(details_data).encode('utf-8')
    
    # Build the account Merkle tree
    account_tree = MerkleTree(storage)
    account_root = account_tree.add([address_leaf, details_leaf])
    
    return account_root


def update_account(storage: Storage, account_root: bytes, account: Account) -> bytes:
    """
    Updates an existing account in the Merkle tree structure.
    
    Args:
        storage: Storage instance
        account_root: Existing account root hash
        account: Updated account data
        
    Returns:
        New root hash of the account tree
    """
    from ..storage.merkle import MerkleTree, find_first
    import json
    
    # First, find the details node
    def is_details_node(node_data: bytes) -> bool:
        try:
            data = json.loads(node_data.decode('utf-8'))
            return data.get('type') == 'details'
        except:
            return False
    
    details_node = find_first(storage, account_root, is_details_node)
    if not details_node:
        # If no details node found, create a new account
        return store_account(storage, account)
    
    # Get the details root
    details_data = json.loads(details_node.decode('utf-8'))
    details_root = bytes.fromhex(details_data.get('root', ''))
    
    # Update each leaf in the details tree
    detail_types = ['balance', 'code', 'counter', 'storage']
    new_leaves = []
    
    for detail_type in detail_types:
        # Find the existing leaf
        def is_matching_leaf(node_data: bytes) -> bool:
            try:
                data = json.loads(node_data.decode('utf-8'))
                return data.get('type') == detail_type
            except:
                return False
        
        leaf_node = find_first(storage, details_root, is_matching_leaf)
        
        # Create updated leaf data
        if detail_type == 'balance':
            leaf_data = {'type': 'balance', 'value': account.balance}
        elif detail_type == 'code':
            leaf_data = {'type': 'code', 'value': account.data.hex() if account.data else ''}
        elif detail_type == 'counter':
            leaf_data = {'type': 'counter', 'value': account.counter}
        elif detail_type == 'storage':
            # Get existing storage value or use empty if not found
            if leaf_node:
                try:
                    existing_data = json.loads(leaf_node.decode('utf-8'))
                    leaf_data = {'type': 'storage', 'value': existing_data.get('value', '')}
                except:
                    leaf_data = {'type': 'storage', 'value': ''}
            else:
                leaf_data = {'type': 'storage', 'value': ''}
        
        new_leaves.append(json.dumps(leaf_data).encode('utf-8'))
    
    # Build new details tree
    details_tree = MerkleTree(storage)
    new_details_root = details_tree.add(new_leaves)
    
    # Update details node
    new_details_data = {'type': 'details', 'root': new_details_root.hex()}
    new_details_leaf = json.dumps(new_details_data).encode('utf-8')
    
    # Find address node
    def is_address_node(node_data: bytes) -> bool:
        try:
            data = json.loads(node_data.decode('utf-8'))
            return data.get('type') == 'address'
        except:
            return False
    
    address_node = find_first(storage, account_root, is_address_node)
    
    # Build new account tree
    account_tree = MerkleTree(storage)
    new_account_root = account_tree.add([address_node, new_details_leaf])
    
    return new_account_root


def get_account_from_tree(storage: Storage, account_root: bytes, address: bytes) -> Optional[Account]:
    """
    Retrieve an account from the account Merkle tree based on the address.
    
    Args:
        storage: Storage instance
        account_root: Root hash of the account tree
        address: Address to find
        
    Returns:
        Account if found, None otherwise
    """
    from ..storage.merkle import find_first
    
    # First find the address node to verify it matches
    def is_matching_address(node_data: bytes) -> bool:
        return node_data == address  # Direct binary comparison 
    
    address_node = find_first(storage, account_root, is_matching_address)
    if not address_node:
        return None
        
    # Extract balance, code, and counter from the tree
    balance = 0
    code = b''
    counter = 0
    
    # Instead of using inefficient search, get the account directly
    account = get_account_from_tree_direct(storage, account_root)
    if not account or account.address != address:
        return None
        
    return account


def build_accounts_state_tree(storage: Storage, accounts: Dict[bytes, Account]) -> bytes:
    """
    Build a complete state tree containing multiple accounts.
    
    Args:
        storage: Storage instance
        accounts: Dictionary mapping addresses to Account objects
        
    Returns:
        Root hash of the state tree
    """
    from ..storage.merkle import MerkleTree
    import json
    
    # Store each account and collect their root hashes
    account_nodes = []
    
    for address, account in accounts.items():
        # Store the account
        account_root = store_account(storage, account)
        
        # Create a state node reference to this account
        state_node_data = {
            'address': address.hex(),
            'account_root': account_root.hex()
        }
        state_node = json.dumps(state_node_data).encode('utf-8')
        account_nodes.append(state_node)
    
    # Build the state tree
    state_tree = MerkleTree(storage)
    state_root = state_tree.add(account_nodes)
    
    return state_root


def get_account_from_state(storage: Storage, state_root: bytes, address: bytes) -> Optional[Account]:
    """
    Retrieve an account from the state tree by address.
    
    Args:
        storage: Storage instance
        state_root: Root hash of the state tree
        address: Address to find
        
    Returns:
        Account if found, None otherwise
    """
    from ..storage.merkle import find_first
    import json
    
    # Find the state node for this address
    def is_matching_state_node(node_data: bytes) -> bool:
        try:
            data = json.loads(node_data.decode('utf-8'))
            return data.get('address') == address.hex()
        except:
            return False
    
    state_node = find_first(storage, state_root, is_matching_state_node)
    if not state_node:
        return None
    
    # Get the account root
    try:
        state_data = json.loads(state_node.decode('utf-8'))
        account_root = bytes.fromhex(state_data.get('account_root', ''))
    except:
        return None
    
    # Get the account from its tree
    return get_account_from_tree(storage, account_root, address)


def update_account_in_state(storage: Storage, state_root: bytes, account: Account) -> bytes:
    """
    Update an account in the state tree or add it if it doesn't exist.
    
    Args:
        storage: Storage instance
        state_root: Root hash of the state tree
        account: Account to update
        
    Returns:
        New root hash of the state tree
    """
    from ..storage.merkle import MerkleTree, find_first, find_all
    import json
    
    # Find all existing state nodes
    def match_all_nodes(node_data: bytes) -> bool:
        return True
    
    all_state_nodes = find_all(storage, state_root, match_all_nodes)
    
    # Check if this account already exists in state
    account_root = None
    existing_node = None
    
    for node in all_state_nodes:
        try:
            data = json.loads(node.decode('utf-8'))
            if data.get('address') == account.address.hex():
                account_root = bytes.fromhex(data.get('account_root', ''))
                existing_node = node
                break
        except:
            continue
    
    # Store or update the account
    if account_root:
        # Update existing account
        new_account_root = update_account(storage, account_root, account)
    else:
        # Store new account
        new_account_root = store_account(storage, account)
    
    # Create or update state node
    state_node_data = {
        'address': account.address.hex(),
        'account_root': new_account_root.hex()
    }
    new_state_node = json.dumps(state_node_data).encode('utf-8')
    
    # If we're updating an existing node
    if existing_node:
        # Replace the node in the list
        new_nodes = []
        for node in all_state_nodes:
            if node == existing_node:
                new_nodes.append(new_state_node)
            else:
                new_nodes.append(node)
    else:
        # Add the new node to the list
        new_nodes = list(all_state_nodes)
        new_nodes.append(new_state_node)
    
    # Build new state tree
    state_tree = MerkleTree(storage)
    new_state_root = state_tree.add(new_nodes)
    
    return new_state_root


def create_account_details_objects(account: Account) -> Dict[bytes, MerkleNode]:
    """
    Creates MerkleNode objects for account details that can be directly stored
    in the storage system.
    
    Args:
        account: The account to create objects for
        
    Returns:
        Dictionary mapping node hashes to MerkleNode objects
    """
    from ..storage.merkle import MerkleNodeType
    
    # Dictionary to store all nodes
    nodes = {}
    
    # Create leaf nodes for each detail
    # Balance leaf - directly use 8-byte representation of balance
    balance_bytes = account.balance.to_bytes(8, 'big')
    balance_node = MerkleNode(
        node_type=MerkleNodeType.LEAF,
        hash=hash_data(b'\x00' + balance_bytes),
        data=balance_bytes
    )
    nodes[balance_node.hash] = balance_node
    
    # Code/data leaf - directly use raw bytes
    code_bytes = account.data if account.data else b''
    code_node = MerkleNode(
        node_type=MerkleNodeType.LEAF,
        hash=hash_data(b'\x00' + code_bytes),
        data=code_bytes
    )
    nodes[code_node.hash] = code_node
    
    # Counter leaf - directly use 8-byte representation of counter
    counter_bytes = account.counter.to_bytes(8, 'big')
    counter_node = MerkleNode(
        node_type=MerkleNodeType.LEAF,
        hash=hash_data(b'\x00' + counter_bytes),
        data=counter_bytes
    )
    nodes[counter_node.hash] = counter_node
    
    # Storage leaf - placeholder for account storage data
    storage_bytes = b''
    storage_node = MerkleNode(
        node_type=MerkleNodeType.LEAF,
        hash=hash_data(b'\x00' + storage_bytes),
        data=storage_bytes
    )
    nodes[storage_node.hash] = storage_node
    
    # Create branch nodes for the details tree
    # First level: balance+code branch
    balance_code_branch = MerkleNode(
        node_type=MerkleNodeType.BRANCH,
        hash=hash_data(b'\x01' + balance_node.hash + code_node.hash),
        left_child=balance_node.hash,
        right_child=code_node.hash
    )
    nodes[balance_code_branch.hash] = balance_code_branch
    
    # First level: counter+storage branch
    counter_storage_branch = MerkleNode(
        node_type=MerkleNodeType.BRANCH,
        hash=hash_data(b'\x01' + counter_node.hash + storage_node.hash),
        left_child=counter_node.hash,
        right_child=storage_node.hash
    )
    nodes[counter_storage_branch.hash] = counter_storage_branch
    
    # Second level: details root
    details_root = MerkleNode(
        node_type=MerkleNodeType.BRANCH,
        hash=hash_data(b'\x01' + balance_code_branch.hash + counter_storage_branch.hash),
        left_child=balance_code_branch.hash,
        right_child=counter_storage_branch.hash
    )
    nodes[details_root.hash] = details_root
    
    # Address leaf node - directly use raw address bytes
    address_bytes = account.address
    address_node = MerkleNode(
        node_type=MerkleNodeType.LEAF,
        hash=hash_data(b'\x00' + address_bytes),
        data=address_bytes
    )
    nodes[address_node.hash] = address_node
    
    # Create the account root node
    account_root = MerkleNode(
        node_type=MerkleNodeType.BRANCH,
        hash=hash_data(b'\x01' + address_node.hash + details_root.hash),
        left_child=address_node.hash,
        right_child=details_root.hash
    )
    nodes[account_root.hash] = account_root
    
    return nodes


def store_account_direct(storage: Storage, account: Account) -> bytes:
    """
    Stores an account directly in storage as MerkleNode objects.
    
    Args:
        storage: Storage instance
        account: Account to store
        
    Returns:
        Root hash of the account tree
    """
    # Create all the nodes
    nodes = create_account_details_objects(account)
    
    # Store all nodes in storage
    for node_hash, node in nodes.items():
        storage.put(node_hash, node.serialize())
    
    # Return the root hash (the last node is the root)
    account_root_hash = None
    for node_hash, node in nodes.items():
        account_root_hash = node_hash  # The last one will be the root
    
    return account_root_hash


def update_account_direct(storage: Storage, account_root_hash: bytes, account: Account) -> bytes:
    """
    Updates an account directly in storage using MerkleNode objects.
    
    Args:
        storage: Storage instance
        account_root_hash: Current root hash of the account
        account: Updated account data
        
    Returns:
        New root hash of the account tree
    """
    from ..storage.merkle import MerkleNodeType
    
    # Get the account root node
    root_data = storage.get(account_root_hash)
    if not root_data:
        # Account doesn't exist, create it
        return store_account_direct(storage, account)
    
    root_node = MerkleNode.deserialize(root_data)
    if root_node.node_type != MerkleNodeType.BRANCH:
        # Invalid root node, create new account
        return store_account_direct(storage, account)
    
    # Create new nodes
    new_nodes = create_account_details_objects(account)
    
    # Store all nodes
    for node_hash, node in new_nodes.items():
        storage.put(node_hash, node.serialize())
    
    # Return the new root hash
    account_root_hash = None
    for node_hash, node in new_nodes.items():
        account_root_hash = node_hash  # The last one will be the root
    
    return account_root_hash


def build_state_tree_direct(storage: Storage, accounts: Dict[bytes, Account]) -> bytes:
    """
    Builds a state tree directly from account objects without using MerkleTree.
    
    Args:
        storage: Storage instance
        accounts: Dictionary mapping addresses to accounts
        
    Returns:
        Root hash of the state tree
    """
    from ..storage.merkle import MerkleNodeType
    import json
    
    # Create state leaf nodes for each account
    state_leaves = []
    
    for address, account in accounts.items():
        # Store the account
        account_root_hash = store_account_direct(storage, account)
        
        # Create state leaf
        state_data = {
            'address': address.hex(),
            'account_root': account_root_hash.hex()
        }
        state_bytes = json.dumps(state_data).encode('utf-8')
        state_leaf = MerkleNode(
            node_type=MerkleNodeType.LEAF,
            hash=hash_data(b'\x00' + state_bytes),
            data=state_bytes
        )
        storage.put(state_leaf.hash, state_leaf.serialize())
        state_leaves.append(state_leaf)
    
    # If no accounts, return None
    if not state_leaves:
        return None
    
    # Build a balanced tree from state leaves
    current_level = state_leaves
    
    while len(current_level) > 1:
        next_level = []
        
        # Process pairs of nodes
        for i in range(0, len(current_level), 2):
            # If we have a pair, create a branch node
            if i + 1 < len(current_level):
                branch = MerkleNode(
                    node_type=MerkleNodeType.BRANCH,
                    hash=hash_data(b'\x01' + current_level[i].hash + current_level[i+1].hash),
                    left_child=current_level[i].hash,
                    right_child=current_level[i+1].hash
                )
            # If we have an odd node left, duplicate it
            else:
                branch = MerkleNode(
                    node_type=MerkleNodeType.BRANCH,
                    hash=hash_data(b'\x01' + current_level[i].hash + current_level[i].hash),
                    left_child=current_level[i].hash,
                    right_child=current_level[i].hash
                )
            
            storage.put(branch.hash, branch.serialize())
            next_level.append(branch)
        
        current_level = next_level
    
    # The last remaining node is the root
    return current_level[0].hash if current_level else None


def get_account_from_tree_direct(storage: Storage, account_root_hash: bytes) -> Optional[Account]:
    """
    Retrieves an account from storage using its root hash, working directly with MerkleNodes.
    
    Args:
        storage: Storage instance
        account_root_hash: Root hash of the account tree
        
    Returns:
        The account if found, None otherwise
    """
    from ..storage.merkle import MerkleNodeType
    
    # Get the account root node
    root_data = storage.get(account_root_hash)
    if not root_data:
        return None
    
    root_node = MerkleNode.deserialize(root_data)
    if root_node.node_type != MerkleNodeType.BRANCH:
        return None
    
    # Get the address node
    address_hash = root_node.left_child
    address_data = storage.get(address_hash)
    if not address_data:
        return None
    
    address_node = MerkleNode.deserialize(address_data)
    if address_node.node_type != MerkleNodeType.LEAF:
        return None
    
    # Address is directly stored as bytes
    address = address_node.data
    
    # Get the details node
    details_hash = root_node.right_child
    details_data = storage.get(details_hash)
    if not details_data:
        return None
    
    details_node = MerkleNode.deserialize(details_data)
    
    # Get values from the details subtree
    balance = 0
    code = b''
    counter = 0
    
    # We need to traverse the details tree to get all values
    if details_node.node_type == MerkleNodeType.BRANCH:
        # Get balance+code branch
        balance_code_hash = details_node.left_child
        balance_code_data = storage.get(balance_code_hash)
        if balance_code_data:
            balance_code_node = MerkleNode.deserialize(balance_code_data)
            
            # Get balance node
            balance_hash = balance_code_node.left_child
            balance_data = storage.get(balance_hash)
            if balance_data:
                balance_node = MerkleNode.deserialize(balance_data)
                balance = int.from_bytes(balance_node.data, 'big')
            
            # Get code node
            code_hash = balance_code_node.right_child
            code_data = storage.get(code_hash)
            if code_data:
                code_node = MerkleNode.deserialize(code_data)
                code = code_node.data
        
        # Get counter+storage branch
        counter_storage_hash = details_node.right_child
        counter_storage_data = storage.get(counter_storage_hash)
        if counter_storage_data:
            counter_storage_node = MerkleNode.deserialize(counter_storage_data)
            
            # Get counter node
            counter_hash = counter_storage_node.left_child
            counter_data = storage.get(counter_hash)
            if counter_data:
                counter_node = MerkleNode.deserialize(counter_data)
                counter = int.from_bytes(counter_node.data, 'big')
    
    # Create the account with the retrieved values
    return Account(
        address=address,
        balance=balance,
        counter=counter,
        data=code
    )
