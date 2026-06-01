from __future__ import annotations

from ...machine.models.expression import ZERO32


def make_search_variants(tx_hash: bytes, sender: bytes,
                         receiver: bytes, key: bytes = ZERO32) -> list[bytes]:
    """Build 7 forced-combinatorial search variants (128 bytes each)."""
    z = b"\x00" * 32
    tx_hash = tx_hash or z
    sender = sender or z
    receiver = receiver or z
    key = key or z
    return [
        tx_hash + z + z + z,
        z + sender + z + z,
        z + z + receiver + z,
        tx_hash + sender + z + z,
        tx_hash + z + receiver + z,
        z + sender + receiver + z,
        tx_hash + sender + receiver + z,
    ]
