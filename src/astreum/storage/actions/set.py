from __future__ import annotations

from typing import Iterable, Tuple


def add_expr_advertisement(
    self,
    expr_id: bytes,
    payload_type: int,
    expires_at: float | None = None,
) -> None:
    """Track an expr id for periodic advertisement."""
    entry = (expr_id, payload_type, expires_at)
    with self.expr_advertisements_lock:
        self.expr_advertisements.append(entry)


def add_expr_advertisements(
    self,
    entries: Iterable[Tuple[bytes, int, float | None]],
) -> None:
    """Track multiple expr ids for periodic advertisement."""
    with self.expr_advertisements_lock:
        self.expr_advertisements.extend(entries)