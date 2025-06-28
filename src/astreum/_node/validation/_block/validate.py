# Cached verified blocks
verified_blocks = set()

def validate_block(block: Block, accounts: Dict[bytes, Account], 
                 known_blocks: Dict[bytes, Block]) -> bool:
    """
    Validate a block.
    
    Args:
        block: Block to validate
        accounts: Dictionary of accounts
        known_blocks: Dictionary of known blocks
        
    Returns:
        True if block is valid, False otherwise
    """
    # Skip validation if already verified
    block_hash = block.get_hash()
    if block_hash in verified_blocks:
        return True
        
    # Check block structure
    if not _validate_block_structure(block):
        return False
        
    # Check if previous block exists, except for genesis block
    if block.number > 0 and block.previous not in known_blocks:
        return False
        
    # Check if validator is a validator
    if not _is_valid_producer(block, accounts):
        return False
        
    # Validate VDF proof
    if not _validate_vdf_proof(block):
        return False
        
    # Validate transactions
    if not _validate_transactions(block, accounts):
        return False
        
    # All checks passed, mark as verified
    verified_blocks.add(block_hash)
    return True

def _validate_block_structure(block: Block) -> bool:
    """
    Validate basic block structure.
    
    Args:
        block: Block to validate
        
    Returns:
        True if structure is valid, False otherwise
    """
    # Check for required fields
    if (block.number is None or block.time is None or 
        not hasattr(block, 'validator') or not block.validator):
        return False
        
    # Check that genesis block has no previous
    if block.number == 0 and block.previous is not None:
        return False
        
    # Check that non-genesis block has previous
    if block.number > 0 and block.previous is None:
        return False
        
    # Check timestamp is reasonable
    current_time = int(time.time())
    if block.time > current_time + 60:  # Allow 1 minute clock drift
        return False
        
    return True

def _is_valid_producer(block: Block, accounts: Dict[bytes, Account]) -> bool:
    """
    Check if block validator is a valid validator.
    
    Args:
        block: Block to validate
        accounts: Dictionary of accounts
        
    Returns:
        True if validator is valid, False otherwise
    """
    # Anyone can produce the genesis block
    if block.number == 0:
        return True
        
    # Check if validator is a validator with stake
    if not block.validator or not hasattr(block.validator, 'public_key'):
        return False
        
    validator_address = block.validator.public_key
    stake = get_validator_stake(accounts, validator_address)
    return stake >= MIN_STAKE_AMOUNT

def _validate_vdf_proof(block: Block) -> bool:
    """
    Validate the VDF proof in the block.
    
    Args:
        block: Block to validate
        
    Returns:
        True if VDF proof is valid, False otherwise
    """
    # Skip VDF validation for genesis block
    if block.number == 0:
        return True
        
    # In a real implementation, this would verify the VDF proof
    # For our purposes, we'll assume all blocks have valid VDF proofs
    if not block.vdf_proof:
        return False
        
    return validate_block_vdf(block.number, block.previous, block.vdf_proof)

def _validate_transactions(block: Block, accounts: Dict[bytes, Account]) -> bool:
    """
    Validate transactions in a block.
    
    Args:
        block: Block to validate
        accounts: Dictionary of accounts
        
    Returns:
        True if all transactions are valid, False otherwise
    """
    # In a real implementation, this would verify each transaction
    # For our purposes, we'll assume all transactions in a block are valid
    return True

def select_validator(accounts: Dict[bytes, Account], random_seed: bytes) -> Optional[bytes]:
    """
    Select a validator based on stake using a random seed.
    
    Args:
        accounts: Dictionary of accounts
        random_seed: Random seed for selection
        
    Returns:
        Selected validator address or None if no validators
    """
    # Get validators (accounts with stake)
    validators = {addr: acc for addr, acc in accounts.items() 
                 if get_validator_stake(accounts, addr) >= MIN_STAKE_AMOUNT}
    
    # Calculate total stake
    total_stake = sum(get_validator_stake(accounts, addr) for addr in validators)
    
    if total_stake <= 0:
        return None
        
    # Convert random seed to a number between 0 and total_stake
    seed_hash = hash_data(random_seed)
    random_value = int.from_bytes(seed_hash, byteorder='big') % total_stake
    
    # Build cumulative stake mapping
    cumulative_stake = 0
    stake_map = {}
    
    # Sort validators by address for determinism
    for addr in sorted(validators.keys()):
        cumulative_stake += get_validator_stake(accounts, addr)
        stake_map[addr] = cumulative_stake
        
    # Find the validator whose cumulative stake covers the random value
    for addr, cum_stake in stake_map.items():
        if random_value < cum_stake:
            return addr
            
    # If no validator found (should not happen), return the last one
    if stake_map:
        return list(stake_map.keys())[-1]
    return None

def select_validator_for_slot(accounts: Dict[bytes, Account], slot: int, 
                             previous_vdf: bytes) -> Optional[bytes]:
    """
    Select validator for a specific slot.
    
    Args:
        accounts: Dictionary of accounts
        slot: Slot number
        previous_vdf: VDF output from previous block
        
    Returns:
        Selected validator address or None if no validators
    """
    # Generate random seed based on slot and previous VDF
    seed = hash_data(previous_vdf + slot.to_bytes(8, byteorder='big'))
    
    # Select validator based on stake
    return select_validator(accounts, seed)
