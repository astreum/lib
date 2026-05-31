import threading
from typing import Optional


class MeterExceededError(Exception):
    """Raised when a Meter's limit is exceeded during charge_bytes."""


class Meter:
    def __init__(self, enabled: bool, limit: Optional[int]):
        self.enabled = enabled
        self.limit: Optional[int] = limit
        self.used: int = 0
        self._lock = threading.Lock()

    def charge_bytes(self, n: int) -> bool:
        if not self.enabled:
            return True
        with self._lock:
            if n < 0:
                n = 0
            if self.limit is not None and (self.used + n) > self.limit:
                raise MeterExceededError(
                    f"meter limit {self.limit} exceeded "
                    f"(used={self.used}, attempted +{n})"
                )
            self.used += n
            return True
