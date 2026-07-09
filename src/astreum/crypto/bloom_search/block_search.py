from __future__ import annotations

from typing import Any, Optional

from astreum.expression import ZERO32
from astreum.storage.get.single import get_expr
from astreum.consensus.models.block import Block
from astreum.crypto.bloom_search.search import ERA_SIZE


def find_block_by_height(astreum_node: Any, *,
                         starting_block=None,
                         target_height: int) -> Optional[Block]:
    """Find a block by height using the bloom tree's binary tree structure.

    Walks backward from starting_block to find the era containing target_height,
    then binary-descents the bloom tree by offset (not by bloom test) to locate
    the leaf containing the target block's expr hash.

    Returns None if the block hasn't been mined yet or isn't reachable
    (e.g. target_height > starting_block.height).
    """
    if starting_block is None:
        return None
    if target_height > starting_block.height:
        return None

    target_era = target_height // ERA_SIZE
    target_offset = target_height % ERA_SIZE

    # Walk backward via previous_block chain until we find a block in the
    # target era.  The first hit is the highest block we have in that era
    # (its bloom_tree is the most complete).
    current = starting_block
    while current is not None and current.height // ERA_SIZE > target_era:
        current = current.previous_block

    if current is None or current.height // ERA_SIZE != target_era:
        return None  # target era not reachable from this starting block

    # Fast path: current IS the target block (e.g. genesis, era head).
    if current.height == target_height:
        return current

    # Check whether the target offset has been mined.
    if target_offset > current.height % ERA_SIZE:
        return None

    # No bloom tree — walk previous_block chain to find the target.
    if not current.bloom_hash or current.bloom_hash == ZERO32:
        target = current
        while target is not None and target.height > target_height:
            if target.previous_block is not None:
                target = target.previous_block
            else:
                prev_hash = getattr(target, "previous_block_hash", None)
                if prev_hash:
                    target = Block.from_storage(astreum_node, prev_hash)
                else:
                    target = None
        return target

    # Binary-descent by offset to locate the leaf's start_hash.
    leaf_hash = _storage_find_leaf(astreum_node, current.bloom_hash, target_offset)
    if leaf_hash is not None:
        return Block.from_storage(astreum_node, leaf_hash)

    # Leaf found but start_hash deferred — target is the era head itself.
    # Walk backward from current to find it.
    target = current
    while target is not None and target.height > target_height:
        if target.previous_block is not None:
            target = target.previous_block
        else:
            prev_hash = getattr(target, "previous_block_hash", None)
            if prev_hash:
                target = Block.from_storage(astreum_node, prev_hash)
            else:
                target = None
    return target


def _storage_find_leaf(astreum_node: Any, root_hash: bytes,
                       offset: int) -> Optional[bytes]:
    """Binary-descent by *position* (not bloom test) in the bloom tree.

    Fetches nodes on demand from storage.  Returns the leaf's ``start_hash``
    (the block's expr hash), or ``None`` if the path doesn't exist (block not
    mined) or the leaf's start_hash hasn't been set yet (deferred).
    """
    from astreum.crypto.bloom_tree.expr import bloom_node_from_expr

    root_expr = get_expr(astreum_node, root_hash)
    if root_expr is None:
        return None
    node = bloom_node_from_expr(root_expr)

    lo, hi = 0, ERA_SIZE

    while not node.is_leaf:
        mid = (lo + hi) // 2
        child_hash = node._left_hash if offset < mid else node._right_hash
        if child_hash is None:
            return None  # path doesn't exist — block at this offset not mined
        child_expr = get_expr(astreum_node, child_hash)
        if child_expr is None:
            return None
        node = bloom_node_from_expr(child_expr)
        lo, hi = (lo, mid) if offset < mid else (mid, hi)

    return node.start_hash
