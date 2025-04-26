"""
Block validation module for the Astreum blockchain.
"""

from .model import Block
from .create import create_block, create_genesis_block

__all__ = [
    'Block',
    'create_block',
    'create_genesis_block',
]