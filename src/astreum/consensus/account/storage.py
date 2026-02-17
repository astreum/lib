from __future__ import annotations

from typing import Any

from ...utils.integer import bytes_to_int
from .create import create_account
from .model import Account


def get_account_from_storage(node: Any, atom_id: bytes) -> Account:
    account_atoms = node.get_atom_list(atom_id)

    if account_atoms is None or len(account_atoms) != 6:
        raise ValueError("malformed account atom list")

    type_atom, balance_atom, channels_atom, code_atom, counter_atom, data_atom = account_atoms
    if type_atom.data != b"account":
        raise ValueError("not an account (type mismatch)")

    account = create_account(
        balance=bytes_to_int(balance_atom.data),
        data_hash=data_atom.data,
        channels_hash=channels_atom.data,
        counter=bytes_to_int(counter_atom.data),
        code_hash=code_atom.data,
    )
    return account
