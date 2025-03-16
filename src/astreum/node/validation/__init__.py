"""
Validation module for the Astreum blockchain.

This module provides functions for validating blocks and transactions,
computing and verifying VDFs, and selecting validators.
"""

# Export validation functions
from .block import (
    validate_block,
    create_block,
    create_genesis_block,
    select_validator,
    select_validator_for_slot
)

# Export VDF functions
from .vdf import (
    compute_vdf,
    verify_vdf,
    validate_block_vdf
)

# Export account functions
from .account import (
    Account,
    get_validator_stake,
    is_validator
)

# Export constants
from .constants import (
    VALIDATION_ADDRESS,
    BURN_ADDRESS,
    MIN_STAKE_AMOUNT,
    SLOT_DURATION,
    VDF_DIFFICULTY
)

# Export blockchain state functions
from .state import (
    add_block_to_state,
    validate_and_apply_block,
    create_account_state,
    get_validator_for_slot,
    select_best_chain,
    compare_chains,
    get_validator_set
)

__all__ = [
    # Block validation
    'validate_block',
    'create_block',
    'create_genesis_block',
    'select_validator',
    'select_validator_for_slot',
    
    # VDF functions
    'compute_vdf',
    'verify_vdf',
    'validate_block_vdf',
    
    # Account functions
    'Account',
    'get_validator_stake',
    'is_validator',
    
    # Constants
    'VALIDATION_ADDRESS',
    'BURN_ADDRESS',
    'MIN_STAKE_AMOUNT',
    'SLOT_DURATION',
    'VDF_DIFFICULTY',
    
    # Blockchain state
    'add_block_to_state',
    'validate_and_apply_block',
    'create_account_state',
    'get_validator_for_slot',
    'select_best_chain',
    'compare_chains',
    'get_validator_set'
]
