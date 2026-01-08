from __future__ import annotations

from blake3 import blake3

NONCE_SIZE = 8
MAX_MESSAGE_NONCE = (1 << (NONCE_SIZE * 8)) - 1


def _leading_zero_bits(buf: bytes) -> int:
    """Return the number of leading zero bits in the provided buffer."""
    zeros = 0
    for byte in buf:
        if byte == 0:
            zeros += 8
            continue
        zeros += 8 - int(byte).bit_length()
        break
    return zeros


def calculate_message_nonce(message_bytes: bytes, difficulty: int) -> int:
    """Find a nonce such that blake3(message_bytes + nonce_bytes) meets difficulty.

    message_bytes should exclude any nonce prefix that will be added on the wire.
    """
    target = max(1, int(difficulty))
    nonce = 0
    message_bytes = bytes(message_bytes)
    while True:
        if nonce > MAX_MESSAGE_NONCE:
            raise ValueError("nonce search exhausted")
        nonce_bytes = int(nonce).to_bytes(NONCE_SIZE, "big", signed=False)
        digest = blake3(message_bytes + nonce_bytes).digest()
        if _leading_zero_bits(digest) >= target:
            return nonce
        nonce += 1
