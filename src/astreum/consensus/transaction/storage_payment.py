from __future__ import annotations

from typing import Any

from .model import Transaction


def handle_storage_payment_contract(
    *,
    node: Any,
    block: object,
    transaction: Transaction,
    sender_account: Any,
    burn_account: Any,
    payload: bytes,
) -> None:
    """Handle a storage-payment contract transaction sent to burn address."""
    pass
