from __future__ import annotations

from typing import Optional

from .model import Transaction


def create_transaction(
    chain_id: int,
    amount: int,
    counter: int,
    recipient: bytes,
    sender: bytes,
    signature: Optional[bytes] = None,
    body_hash: Optional[bytes] = None,
    atom_hash: Optional[bytes] = None,
    version: int = 1,
    data: bytes = b"",
) -> Transaction:
    transaction = Transaction(
        chain_id=chain_id,
        amount=amount,
        counter=counter,
        version=version,
        data=data,
        recipient=recipient,
        sender=sender,
        signature=signature,
        body_hash=body_hash,
        atom_hash=atom_hash,
        hash=atom_hash,
    )
    return transaction
