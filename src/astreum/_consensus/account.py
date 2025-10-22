from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

from .._storage.atom import Atom, ZERO32
from .._storage.patricia import PatriciaTrie
from ..utils.integer import bytes_to_int, int_to_bytes


@dataclass
class Account:
    balance: int
    code: bytes
    counter: int
    data_hash: bytes
    data: PatriciaTrie
    hash: bytes = ZERO32
    body_hash: bytes = ZERO32
    atoms: List[Atom] = field(default_factory=list)

    @classmethod
    def create(cls, balance: int = 0, data_hash: bytes = ZERO32, code: bytes = ZERO32, counter: int = 0) -> "Account":
        account = cls(
            balance=int(balance),
            code=bytes(code),
            counter=int(counter),
            data_hash=bytes(data_hash),
            data=PatriciaTrie(root_hash=bytes(data_hash)),
        )
        account.to_atom()
        return account

    @classmethod
    def from_atom(cls, node: Any, account_id: bytes) -> "Account":
        storage_get = node._local_get

        type_atom = storage_get(account_id)
        if type_atom is None or type_atom.data != b"account":
            raise ValueError("not an account (type mismatch)")

        def _read_atom(atom_id: Optional[bytes]) -> Optional[Atom]:
            if not atom_id or atom_id == ZERO32:
                return None
            return storage_get(atom_id)

        balance_atom = _read_atom(type_atom.next)
        if balance_atom is None:
            raise ValueError("malformed account (balance missing)")

        code_atom = _read_atom(balance_atom.next)
        if code_atom is None:
            raise ValueError("malformed account (code missing)")

        counter_atom = _read_atom(code_atom.next)
        if counter_atom is None:
            raise ValueError("malformed account (counter missing)")

        data_atom = _read_atom(counter_atom.next)
        if data_atom is None:
            raise ValueError("malformed account (data missing)")

        account = cls.create(
            balance=bytes_to_int(balance_atom.data),
            data_hash=data_atom.data,
            counter=bytes_to_int(counter_atom.data),
            code=code_atom.data,
        )
        if account.hash != account_id:
            raise ValueError("account hash mismatch while decoding")
        return account

    def to_atom(self) -> Tuple[bytes, List[Atom]]:
        # Build a single forward chain: account -> balance -> code -> counter -> data.
        data_atom = Atom.from_data(data=bytes(self.data_hash))
        counter_atom = Atom.from_data(
            data=int_to_bytes(self.counter),
            next_hash=data_atom.object_id(),
        )
        code_atom = Atom.from_data(
            data=bytes(self.code),
            next_hash=counter_atom.object_id(),
        )
        balance_atom = Atom.from_data(
            data=int_to_bytes(self.balance),
            next_hash=code_atom.object_id(),
        )
        type_atom = Atom.from_data(data=b"account", next_hash=balance_atom.object_id())

        atoms = [data_atom, counter_atom, code_atom, balance_atom, type_atom]
        account_hash = type_atom.object_id()
        self.hash = account_hash
        self.body_hash = account_hash
        self.atoms = atoms
        return account_hash, list(atoms)
