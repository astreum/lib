from __future__ import annotations


def _bits_from_payload(payload: bytes, bit_length: int) -> str:
    if bit_length <= 0 or not payload:
        return ""
    bit_stream = "".join(f"{byte:08b}" for byte in payload)
    return bit_stream[:bit_length]


def _bits_to_bytes(bit_string: str) -> bytes:
    if not bit_string:
        return b""
    pad = (8 - (len(bit_string) % 8)) % 8
    bit_string = bit_string + ("0" * pad)
    byte_len = len(bit_string) // 8
    return int(bit_string, 2).to_bytes(byte_len, "big")
