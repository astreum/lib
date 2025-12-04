from __future__ import annotations

from dataclasses import dataclass


class PingFormatError(ValueError):
    """Raised when ping payload bytes are invalid."""


@dataclass
class Ping:
    is_validator: bool
    latest_block: bytes

    PAYLOAD_SIZE = 33

    def __post_init__(self) -> None:
        lb = bytes(self.latest_block or b"")
        if len(lb) != 32:
            raise ValueError("latest_block must be exactly 32 bytes")
        self.latest_block = lb

    def to_bytes(self) -> bytes:
        return (b"\x01" if self.is_validator else b"\x00") + self.latest_block

    @classmethod
    def from_bytes(cls, data: bytes) -> "Ping":
        if len(data) != cls.PAYLOAD_SIZE:
            raise PingFormatError("ping payload must be exactly 33 bytes")
        flag = data[0]
        if flag not in (0, 1):
            raise PingFormatError("ping validator flag must be 0 or 1")
        return cls(is_validator=bool(flag), latest_block=data[1:])
