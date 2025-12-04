from typing import Optional


class Meter:
    def __init__(self, enabled: bool = True, limit: Optional[int] = None):
        self.enabled = enabled
        self.limit: Optional[int] = limit
        self.used: int = 0

    def charge_bytes(self, n: int) -> bool:
        if not self.enabled:
            return True
        if n < 0:
            n = 0
        if self.limit is not None and (self.used + n) >= self.limit:
            return False
        self.used += n
        return True