"""
Constants for the validation module.
"""

import time
from ..utils import hash_data

# Special addresses
VALIDATION_ADDRESS = b'\xFF' * 32  # Address for staking (all F's)
BURN_ADDRESS = b'\x00' * 32  # Address for burning tokens (all 0's)

# Validation parameters
MIN_STAKE_AMOUNT = 1  # Minimum stake amount in Aster
SLOT_DURATION = 1  # Duration of each slot in seconds
VDF_DIFFICULTY = 1  # Default VDF difficulty
