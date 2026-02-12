from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from ...storage.models.atom import Atom, AtomKind, ZERO32
from ...utils.integer import int_to_bytes
from .from_storage import load_transaction_atoms, load_transaction_from_storage


@dataclass
class Transaction:
    chain_id: int
    amount: int
    counter: int
    version: int = 1
    data: bytes = b""
    recipient: bytes = b""
    sender: bytes = b""
    signature: bytes = b""
    hash: bytes = ZERO32

    def sign(self, private_key: Any) -> bytes:
        """Sign the transaction detail list head and store the signature."""
        detail_payloads: List[bytes] = []

        def emit(payload: bytes) -> None:
            detail_payloads.append(payload)

        emit(int_to_bytes(self.chain_id))
        emit(int_to_bytes(self.amount))
        emit(int_to_bytes(self.counter))
        emit(bytes(self.data))
        emit(bytes(self.recipient))
        emit(bytes(self.sender))

        body_head = ZERO32
        for payload in reversed(detail_payloads):
            atom = Atom(data=payload, next_id=body_head, kind=AtomKind.BYTES)
            body_head = atom.object_id()

        self.signature = private_key.sign(body_head)
        return body_head

    def atomize(self) -> Tuple[bytes, List[Atom]]:
        """Serialise the transaction, returning (object_id, atoms)."""
        detail_payloads: List[bytes] = []
        acc: List[Atom] = []

        def emit(payload: bytes) -> None:
            detail_payloads.append(payload)

        emit(int_to_bytes(self.chain_id))
        emit(int_to_bytes(self.amount))
        emit(int_to_bytes(self.counter))
        emit(bytes(self.data))
        emit(bytes(self.recipient))
        emit(bytes(self.sender))

        body_head = ZERO32
        detail_atoms: List[Atom] = []
        for payload in reversed(detail_payloads):
            atom = Atom(data=payload, next_id=body_head, kind=AtomKind.BYTES)
            detail_atoms.append(atom)
            body_head = atom.object_id()
        detail_atoms.reverse()
        acc.extend(detail_atoms)

        body_list_atom = Atom(data=body_head, kind=AtomKind.LIST)
        acc.append(body_list_atom)
        body_list_id = body_list_atom.object_id()

        signature_atom = Atom(
            data=bytes(self.signature),
            next_id=body_list_id,
            kind=AtomKind.BYTES,
        )
        version_atom = Atom(
            data=int_to_bytes(self.version),
            next_id=signature_atom.object_id(),
            kind=AtomKind.BYTES,
        )
        type_atom = Atom(
            data=b"transaction",
            next_id=version_atom.object_id(),
            kind=AtomKind.SYMBOL,
        )

        acc.append(signature_atom)
        acc.append(version_atom)
        acc.append(type_atom)

        self.hash = type_atom.object_id()
        return self.hash, acc

    @classmethod
    def from_storage(
        cls,
        node: Any,
        transaction_id: bytes,
    ) -> Transaction:
        return load_transaction_from_storage(cls, node, transaction_id)

    @classmethod
    def get_atoms(
        cls,
        node: Any,
        transaction_id: bytes,
    ) -> Optional[List[Atom]]:
        """Load the transaction atom chain from storage, returning the atoms or None."""
        return load_transaction_atoms(node, transaction_id)
