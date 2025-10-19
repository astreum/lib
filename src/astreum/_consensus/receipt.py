from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from .._storage.atom import Atom, ZERO32

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


def _make_list(child_ids: List[bytes]) -> Tuple[bytes, List[Atom]]:
    atoms: List[Atom] = []
    next_hash = ZERO32
    elements: List[Atom] = []
    for child_id in reversed(child_ids):
        elem = Atom.from_data(data=child_id, next_hash=next_hash)
        next_hash = elem.object_id()
        elements.append(elem)
    elements.reverse()
    list_value = Atom.from_data(data=len(child_ids).to_bytes(8, "little"), next_hash=next_hash)
    list_type = Atom.from_data(data=b"list", next_hash=list_value.object_id())
    atoms.extend(elements)
    atoms.append(list_value)
    atoms.append(list_type)
    return list_type.object_id(), atoms


def _read_list_entries(
    storage_get: Callable[[bytes], Optional[Atom]], start: bytes
) -> List[bytes]:
    entries: List[bytes] = []
    current = start if start and start != ZERO32 else b""
    while current:
        elem = storage_get(current)
        if elem is None:
            break
        entries.append(elem.data)
        nxt = elem.next
        current = nxt if nxt and nxt != ZERO32 else b""
    return entries


def _read_payload_bytes(
    storage_get: Callable[[bytes], Optional[Atom]], object_id: bytes
) -> bytes:
    if not object_id or object_id == ZERO32:
        return b""
    atom = storage_get(object_id)
    if atom is None:
        return b""
    if atom.data == b"bytes":
        value_atom = storage_get(atom.next)
        return value_atom.data if value_atom is not None else b""
    return atom.data


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

        atoms: List[Atom] = []

        tx_atom = Atom.from_data(data=bytes(self.transaction_hash))
        status_atom = Atom.from_data(data=_int_to_be_bytes(self.status))
        cost_atom = Atom.from_data(data=_int_to_be_bytes(self.cost))
        logs_atom = Atom.from_data(data=bytes(self.logs))

        atoms.extend([tx_atom, status_atom, cost_atom, logs_atom])

        body_child_ids = [
            tx_atom.object_id(),
            status_atom.object_id(),
            cost_atom.object_id(),
            logs_atom.object_id(),
        ]
        body_id, body_atoms = _make_list(body_child_ids)
        atoms.extend(body_atoms)

        type_atom = Atom.from_data(data=b"receipt", next_hash=body_id)
        atoms.append(type_atom)

        top_list_id, top_atoms = _make_list([type_atom.object_id(), body_id])
        atoms.extend(top_atoms)

        return top_list_id, atoms

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
        top_type_atom = storage_get(receipt_id)
        if top_type_atom is None or top_type_atom.data != b"list":
            raise ValueError("not a receipt (outer list missing)")

        top_value_atom = storage_get(top_type_atom.next)
        if top_value_atom is None:
            raise ValueError("malformed receipt (outer value missing)")

        head = top_value_atom.next
        first_elem = storage_get(head) if head else None
        if first_elem is None:
            raise ValueError("malformed receipt (type element missing)")

        type_atom_id = first_elem.data
        type_atom = storage_get(type_atom_id)
        if type_atom is None or type_atom.data != b"receipt":
            raise ValueError("not a receipt (type mismatch)")

        remainder_entries = _read_list_entries(storage_get, first_elem.next)
        if not remainder_entries:
            raise ValueError("malformed receipt (body missing)")
        body_id = remainder_entries[0]

        body_type_atom = storage_get(body_id)
        if body_type_atom is None or body_type_atom.data != b"list":
            raise ValueError("malformed receipt body (type)")

        body_value_atom = storage_get(body_type_atom.next)
        if body_value_atom is None:
            raise ValueError("malformed receipt body (value)")

        body_entries = _read_list_entries(storage_get, body_value_atom.next)
        if len(body_entries) < 4:
            body_entries.extend([ZERO32] * (4 - len(body_entries)))

        transaction_hash_bytes = _read_payload_bytes(storage_get, body_entries[0])
        status_bytes = _read_payload_bytes(storage_get, body_entries[1])
        cost_bytes = _read_payload_bytes(storage_get, body_entries[2])
        logs_bytes = _read_payload_bytes(storage_get, body_entries[3])
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
