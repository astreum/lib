from __future__ import annotations


def _bit(buf: bytes, idx: int) -> bool:
    byte_i, offset = divmod(idx, 8)
    return ((buf[byte_i] >> (7 - offset)) & 1) == 1


def _match_prefix(
    prefix: bytes,
    prefix_len: int,
    key: bytes,
    key_bit_offset: int,
) -> bool:
    total_bits = len(key) * 8
    if key_bit_offset + prefix_len > total_bits:
        return False
    for i in range(prefix_len):
        if _bit(prefix, i) != _bit(key, key_bit_offset + i):
            return False
    return True


def _bit_slice(
    buf: bytes,
    start_bit: int,
    length: int
) -> tuple[bytes, int]:
    if length == 0:
        return b"", 0

    total = int.from_bytes(buf, "big")
    bits_in_buf = len(buf) * 8

    shift = bits_in_buf - (start_bit + length)
    slice_int = (total >> shift) & ((1 << length) - 1)

    pad = (8 - (length % 8)) % 8
    slice_int <<= pad
    byte_len = (length + 7) // 8
    return slice_int.to_bytes(byte_len, "big"), length
