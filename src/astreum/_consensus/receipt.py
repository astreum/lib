from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from .._storage.atom import Atom, AtomKind, ZERO32

STATUS_SUCCESS = 0
STATUS_FAILED = 1


def _int_to_be_bytes(value: Optional[int]) -> bytes:
    if value is None:
        return b""
    value = int(value)
    if value == 0:
        return b"\x00"
    size = (value.bit_length() + 7) // 8
    return value.to_bytes(size, "big")


def _be_bytes_to_int(data: Optional[bytes]) -> int:
    if not data:
        return 0
    return int.from_bytes(data, "big")


@dataclass
class Receipt:
    transaction_hash: bytes = ZERO32
    cost: int = 0
    logs: bytes = b""
    status: int = 0
    hash: bytes = ZERO32
    atoms: List[Atom] = field(default_factory=list)

    def to_atom(self) -> Tuple[bytes, List[Atom]]:
        """Serialise the receipt into Atom storage."""
        if self.status not in (STATUS_SUCCESS, STATUS_FAILED):
            raise ValueError("unsupported receipt status")

        detail_specs = [
            (bytes(self.transaction_hash), AtomKind.LIST),
            (_int_to_be_bytes(self.status), AtomKind.BYTES),
            (_int_to_be_bytes(self.cost), AtomKind.BYTES),
            (bytes(self.logs), AtomKind.BYTES),
        ]

        detail_atoms: List[Atom] = []
        next_hash = ZERO32
        for payload, kind in reversed(detail_specs):
            atom = Atom.from_data(data=payload, next_hash=next_hash, kind=kind)
            detail_atoms.append(atom)
            next_hash = atom.object_id()
        detail_atoms.reverse()

        type_atom = Atom.from_data(
            data=b"receipt",
            next_hash=next_hash,
            kind=AtomKind.SYMBOL,
        )

        self.hash = type_atom.object_id()
        atoms = detail_atoms + [type_atom]
        return self.hash, atoms

    def atomize(self) -> Tuple[bytes, List[Atom]]:
        """Generate atoms for this receipt and cache them."""
        receipt_id, atoms = self.to_atom()
        self.hash = receipt_id
        self.atoms = atoms
        return receipt_id, atoms

    @classmethod
    def from_atom(
        cls,
        storage_get: Callable[[bytes], Optional[Atom]],
        receipt_id: bytes,
    ) -> Receipt:
        """Materialise a Receipt from Atom storage."""
        def _atom_kind(atom: Optional[Atom]) -> Optional[AtomKind]:
            kind_value = getattr(atom, "kind", None)
            if isinstance(kind_value, AtomKind):
                return kind_value
            if isinstance(kind_value, int):
                try:
                    return AtomKind(kind_value)
                except ValueError:
                    return None
            return None

        type_atom = storage_get(receipt_id)
        if type_atom is None:
            raise ValueError("missing receipt type atom")
        if _atom_kind(type_atom) is not AtomKind.SYMBOL:
            raise ValueError("malformed receipt (type kind)")
        if type_atom.data != b"receipt":
            raise ValueError("not a receipt (type payload)")

        details: List[Atom] = []
        current = type_atom.next
        while current and current != ZERO32 and len(details) < 4:
            atom = storage_get(current)
            if atom is None:
                raise ValueError("missing receipt detail atom")
            details.append(atom)
            current = atom.next

        if current and current != ZERO32:
            raise ValueError("too many receipt fields")
        if len(details) != 4:
            raise ValueError("incomplete receipt fields")

        tx_atom, status_atom, cost_atom, logs_atom = details

        if _atom_kind(tx_atom) is not AtomKind.LIST:
            raise ValueError("receipt transaction hash must be list-kind")
        if any(_atom_kind(atom) is not AtomKind.BYTES for atom in [status_atom, cost_atom, logs_atom]):
            raise ValueError("receipt detail atoms must be bytes-kind")

        transaction_hash_bytes = tx_atom.data or ZERO32
        status_bytes = status_atom.data
        cost_bytes = cost_atom.data
        logs_bytes = logs_atom.data

        status_value = _be_bytes_to_int(status_bytes)
        if status_value not in (STATUS_SUCCESS, STATUS_FAILED):
            raise ValueError("unsupported receipt status")

        return cls(
            transaction_hash=transaction_hash_bytes or ZERO32,
            cost=_be_bytes_to_int(cost_bytes),
            logs=logs_bytes,
            status=status_value,
            hash=bytes(receipt_id),
        )
