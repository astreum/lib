from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Tuple

from .._storage.atom import Atom, ZERO32


def _int_to_be_bytes(value: int) -> bytes:
    value = int(value)
    if value < 0:
        raise ValueError("account integers must be non-negative")
    if value == 0:
        return b"\x00"
    size = (value.bit_length() + 7) // 8
    return value.to_bytes(size, "big")


def _be_bytes_to_int(data: Optional[bytes]) -> int:
    if not data:
        return 0
    return int.from_bytes(data, "big")


def _make_list(child_ids: List[bytes]) -> Tuple[bytes, List[Atom]]:
    next_hash = ZERO32
    elements: List[Atom] = []
    for child_id in reversed(child_ids):
        elem = Atom.from_data(data=child_id, next_hash=next_hash)
        next_hash = elem.object_id()
        elements.append(elem)
    elements.reverse()
    value_atom = Atom.from_data(
        data=len(child_ids).to_bytes(8, "little"),
        next_hash=next_hash,
    )
    type_atom = Atom.from_data(data=b"list", next_hash=value_atom.object_id())
    atoms = elements + [value_atom, type_atom]
    return type_atom.object_id(), atoms


def _resolve_storage_get(source: Any) -> Callable[[bytes], Optional[Atom]]:
    if callable(source):
        return source
    getter = getattr(source, "_local_get", None)
    if callable(getter):
        return getter
    raise TypeError("Account.from_atom needs a callable storage getter or node with '_local_get'")


def _read_list_entries(
    storage_get: Callable[[bytes], Optional[Atom]],
    start: bytes,
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


@dataclass
class Account:
    _balance: int
    _data: bytes
    _nonce: int
    hash: bytes = ZERO32
    atoms: List[Atom] = field(default_factory=list)

    @staticmethod
    def _encode(balance: int, data: bytes, nonce: int) -> Tuple[bytes, List[Atom]]:
        balance_atom = Atom.from_data(data=_int_to_be_bytes(balance))
        data_atom = Atom.from_data(data=bytes(data))
        nonce_atom = Atom.from_data(data=_int_to_be_bytes(nonce))

        field_atoms = [balance_atom, data_atom, nonce_atom]
        field_ids = [a.object_id() for a in field_atoms]

        body_id, body_atoms = _make_list(field_ids)
        type_atom = Atom.from_data(data=b"account", next_hash=body_id)
        top_id, top_atoms = _make_list([type_atom.object_id(), body_id])

        atoms = field_atoms + body_atoms + [type_atom] + top_atoms
        return top_id, atoms

    @classmethod
    def create(cls, balance: int, data: bytes, nonce: int) -> "Account":
        account_hash, atoms = cls._encode(balance, data, nonce)
        return cls(
            _balance=int(balance),
            _data=bytes(data),
            _nonce=int(nonce),
            hash=account_hash,
            atoms=atoms,
        )

    @classmethod
    def from_atom(cls, source: Any, account_id: bytes) -> "Account":
        storage_get = _resolve_storage_get(source)

        outer_list = storage_get(account_id)
        if outer_list is None or outer_list.data != b"list":
            raise ValueError("not an account (outer list missing)")

        outer_value = storage_get(outer_list.next)
        if outer_value is None:
            raise ValueError("malformed account (outer value missing)")

        entries = _read_list_entries(storage_get, outer_value.next)
        if len(entries) < 2:
            raise ValueError("malformed account (type/body missing)")

        type_atom_id, body_id = entries[0], entries[1]
        type_atom = storage_get(type_atom_id)
        if type_atom is None or type_atom.data != b"account":
            raise ValueError("not an account (type mismatch)")

        body_list = storage_get(body_id)
        if body_list is None or body_list.data != b"list":
            raise ValueError("malformed account body (type)")

        body_value = storage_get(body_list.next)
        if body_value is None:
            raise ValueError("malformed account body (value)")

        field_ids = _read_list_entries(storage_get, body_value.next)
        if len(field_ids) < 3:
            field_ids.extend([ZERO32] * (3 - len(field_ids)))

        def _read_field(field_id: bytes) -> bytes:
            if not field_id or field_id == ZERO32:
                return b""
            atom = storage_get(field_id)
            return atom.data if atom is not None else b""

        balance_bytes = _read_field(field_ids[0])
        data_bytes = _read_field(field_ids[1])
        nonce_bytes = _read_field(field_ids[2])

        account = cls.create(
            balance=_be_bytes_to_int(balance_bytes),
            data=data_bytes,
            nonce=_be_bytes_to_int(nonce_bytes),
        )
        if account.hash != account_id:
            raise ValueError("account hash mismatch while decoding")
        return account

    def balance(self) -> int:
        return self._balance

    def data(self) -> bytes:
        return self._data

    def nonce(self) -> int:
        return self._nonce

    def body_hash(self) -> bytes:
        return self.hash

    def to_atom(self) -> Tuple[bytes, List[Atom]]:
        account_hash, atoms = self._encode(self._balance, self._data, self._nonce)
        self.hash = account_hash
        self.atoms = atoms
        return account_hash, list(atoms)
