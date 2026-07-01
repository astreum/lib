import threading
from typing import Optional


class MeterExceededError(Exception):
    """Raised when a Meter's limit is exceeded during charge."""


class Meter:
    def __init__(self, limit: Optional[int] = None):
        self.limit: Optional[int] = limit
        self.eval: int = 0
        self.storage: int = 0
        self._lock = threading.Lock()

    @property
    def total(self) -> int:
        return self.eval + self.storage

    def charge(self, n: int, kind: str = "eval") -> bool:
        if self.limit is None:
            return True
        with self._lock:
            if n < 0:
                n = 0
            if (self.total + n) > self.limit:
                raise MeterExceededError(
                    f"meter limit {self.limit} exceeded "
                    f"(used={self.total}, attempted +{n})"
                )
            if kind == "eval":
                self.eval += n
            elif kind == "storage":
                self.storage += n
            else:
                raise ValueError(f"unknown meter kind: {kind!r}")
            return True

    def charge_bytes(self, n: int, is_storage: bool = False) -> bool:
        return self.charge(n, kind="storage" if is_storage else "eval")
