from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class PingFormatError(ValueError):
    """Raised when ping payload bytes are invalid."""


@dataclass
class Ping:
    is_validator: bool
    difficulty: int
    latest_block: Optional[bytes]

    PAYLOAD_SIZE = 34
    ZERO_BLOCK = b"\x00" * 32

    def __post_init__(self) -> None:
        self.difficulty = int(self.difficulty)
        if self.difficulty < 1 or self.difficulty > 255:
            raise ValueError("difficulty must be between 1 and 255")
        if self.latest_block is None:
            return
        lb = bytes(self.latest_block)
        if len(lb) != 32:
            raise ValueError("latest_block must be exactly 32 bytes")
        self.latest_block = lb

    def to_bytes(self) -> bytes:
        flag = b"\x01" if self.is_validator else b"\x00"
        difficulty = bytes([self.difficulty])
        latest_block = self.latest_block if self.latest_block is not None else self.ZERO_BLOCK
        return flag + difficulty + latest_block

    @classmethod
    def from_bytes(cls, data: bytes) -> "Ping":
        if len(data) != cls.PAYLOAD_SIZE:
            raise PingFormatError("ping payload must be 34 bytes")
        flag = data[0]
        if flag not in (0, 1):
            raise PingFormatError("ping validator flag must be 0 or 1")
        difficulty = data[1]
        if difficulty < 1:
            raise PingFormatError("ping difficulty must be >= 1")
        latest_block = data[2:]
        if latest_block == cls.ZERO_BLOCK:
            latest_block = None
        return cls(
            is_validator=bool(flag),
            difficulty=difficulty,
            latest_block=latest_block,
        )
