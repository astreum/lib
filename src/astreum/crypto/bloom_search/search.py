from __future__ import annotations

from typing import Any

from ...machine.models.expression import ZERO32
from ..bloom_tree.tree import bloom_search_storage

ERA_SIZE = 1024


def bloom_search_tx(astreum_node: Any, *,
                    tx_hash: bytes = ZERO32,
                    sender: bytes = ZERO32,
                    receiver: bytes = ZERO32,
                    key: bytes = ZERO32,
                    era_start: int = 0,
                    era_end: int | None = None) -> list[bytes]:
    """Search for transactions matching filter args within era range.
    Returns list of matching block hashes."""
    element = _build_element(tx_hash=tx_hash, sender=sender,
                             receiver=receiver, key=key)

    if era_end is None:
        latest = getattr(astreum_node, "latest_block", None)
        era_end = (latest.height // ERA_SIZE) + 1 if latest else era_start + 1

    results: list[bytes] = []

    for era in range(era_end - 1, era_start - 1, -1):
        if era == era_end - 1 and hasattr(astreum_node, "latest_block"):
            bloom_hash = astreum_node.latest_block.bloom_hash
        else:
            transition_height = (era + 1) * ERA_SIZE
            transition_block = _find_block_at_height(astreum_node, transition_height)
            if transition_block is None:
                continue
            bloom_hash = transition_block.previous_era_hash

        if not bloom_hash or bloom_hash == ZERO32:
            continue

        era_results = bloom_search_storage(bloom_hash, element, astreum_node)
        results.extend(era_results)

    return results


def _build_element(*, tx_hash=ZERO32, sender=ZERO32,
                   receiver=ZERO32, key=ZERO32) -> bytes:
    return (tx_hash or ZERO32).ljust(32, b"\x00")[:32] + \
           (sender or ZERO32).ljust(32, b"\x00")[:32] + \
           (receiver or ZERO32).ljust(32, b"\x00")[:32] + \
           (key or ZERO32).ljust(32, b"\x00")[:32]


def _find_block_at_height(node, height):
    """Find a block at a given height by walking from latest_block."""
    latest = getattr(node, "latest_block", None)
    if latest is None:
        return None

    current = latest
    while current is not None and current.height > height:
        current = current.previous_block

    if current is not None and current.height == height:
        return current
    return None
