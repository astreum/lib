from __future__ import annotations

from typing import Any

from ....validation.models.receipt import STATUS_SUCCESS


def handle_treasury_close(
    *,
    node: Any,
    block: object,
    transaction: Any,
) -> int:
    """Stub: handle a treasury loan close transaction."""
    return STATUS_SUCCESS
