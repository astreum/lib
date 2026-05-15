from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from ...storage.models.atom import Atom, AtomKind, ZERO32
from ...utils.integer import int_to_bytes
from .code import TransactionCode, transaction_code_to_bytes
from .from_storage import load_transaction_atoms


@dataclass
class Transaction:
    chain_id: int
    amount: int
    code: TransactionCode
    counter: int
    cost_limit: int = 0
    version: int = 1
    data: bytes = b""
    recipient: bytes = b""
    sender: bytes = b""
    signature: Optional[bytes] = None
    atom_hash: Optional[bytes] = None
    body_hash: Optional[bytes] = None
    hash: Optional[bytes] = None

    def sign(self, private_key: Any) -> bytes:
        """Sign the transaction detail list head and store the signature."""
        detail_payloads: List[bytes] = []

        def emit(payload: bytes) -> None:
            detail_payloads.append(payload)

        emit(int_to_bytes(self.chain_id))
        emit(int_to_bytes(self.amount))
        emit(transaction_code_to_bytes(self.code))
        emit(int_to_bytes(self.counter))
        emit(int_to_bytes(self.cost_limit))
        emit(bytes(self.data))
        emit(bytes(self.recipient))
        emit(bytes(self.sender))

        body_head = ZERO32
        for payload in reversed(detail_payloads):
            atom = Atom(data=payload, next_id=body_head, kind=AtomKind.BYTES)
            body_head = atom.object_id()

        self.signature = private_key.sign(body_head)
        self.body_hash = body_head
        self.atom_hash = None
        self.hash = None
        return body_head

    @staticmethod
    def get_atoms(
        node: Any,
        transaction_id: bytes,
    ) -> Optional[List[Atom]]:
        """Load the transaction atom chain from storage, returning the atoms or None."""
        return load_transaction_atoms(node, transaction_id)
