"""Consensus fork verification helpers."""

from __future__ import annotations

from typing import Any

from ...consensus.block.verify import verify_block_head, verify_block_transactions
from ...storage.models.atom import ZERO32
from ...validation.models.block import Block
from .node import update_fork


def verify_fork(node: Any, head_id: bytes) -> bool:
    """Verify fork headers from head to root."""
    with node.forks_lock:
        fork = node.forks[head_id]
        root = fork.root
    current_hash = head_id
    while True:
        block = Block.from_storage(node, current_hash)
        
        previous_block = None
        if block.previous_block_hash != ZERO32:
            previous_block = Block.from_storage(node, block.previous_block_hash)
        block.previous_block = previous_block
        
        if not verify_block_head(node, block):
            update_fork(node, head_id, {"malicious_block_hash": current_hash})
            return False
        
        with node.forks_lock:
            if current_hash in node.forks and current_hash != head_id:
                fork.header_verified_up_to = current_hash
                fork.root = current_hash
                root = current_hash
                break
        
        if current_hash == root:
            update_fork(node, head_id, {"header_verified_up_to": root})
            break
        
        if block.previous_block_hash == ZERO32:
            update_fork(node, head_id, {"header_verified_up_to": ZERO32, "root": ZERO32})
            root = ZERO32
            break
        
        current_hash = block.previous_block_hash

    current_hash = head_id
    while True:
        block = Block.from_storage(node, current_hash)
        previous_block = None
        if block.previous_block_hash != ZERO32:
            previous_block = Block.from_storage(node, block.previous_block_hash)
        block.previous_block = previous_block
        validator_bytes = node.config.get("validator_secret_key_bytes")
        if validator_bytes and block.validator_public_key_bytes == validator_bytes:
            update_fork(node, head_id, {"transactions_verified_up_to": current_hash})
        elif not verify_block_transactions(node, block):
            update_fork(node, head_id, {"malicious_block_hash": current_hash})
            return False
        else:
            update_fork(node, head_id, {"transactions_verified_up_to": current_hash})
        if current_hash == root or block.previous_block_hash == ZERO32:
            return True
        current_hash = block.previous_block_hash
