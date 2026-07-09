from __future__ import annotations

from astreum.crypto.bloom_filter.insert import _bloom_positions
from astreum.crypto.bloom_filter.main import BloomFilter


def bloom_test(bf: BloomFilter, element: bytes) -> bool:
    """Test if an element may be present. Checks tiers smallest-to-largest, returns
    True on first hit. False means definitely absent."""
    for tier in bf.tiers:
        bits = len(tier) * 8
        positions = _bloom_positions(element, bits)
        if all((tier[pos // 8] >> (pos % 8)) & 1 for pos in positions):
            return True
    return False
