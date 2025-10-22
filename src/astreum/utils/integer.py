from __future__ import annotations

from typing import Optional, Union

ByteLike = Union[bytes, bytearray, memoryview]


def int_to_bytes(value: Optional[int]) -> bytes:
    """Convert an integer to a little-endian byte string with minimal length."""
    if value is None:
        return b""
    value = int(value)
    if value == 0:
        return b"\x00"
    length = (value.bit_length() + 7) // 8
    return value.to_bytes(length, "little", signed=False)


def bytes_to_int(data: Optional[ByteLike]) -> int:
    """Convert a little-endian byte string to an integer."""
    if not data:
        return 0
    if isinstance(data, memoryview):
        data = data.tobytes()
    return int.from_bytes(bytes(data), "little", signed=False)
