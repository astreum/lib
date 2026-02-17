from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

from ...storage.models.atom import Atom, AtomKind
from ...utils.integer import int_to_bytes

if TYPE_CHECKING:
    from .model import Account


def atomize_account(account: "Account") -> Tuple[bytes, List[Atom]]:
    data_atom = Atom(
        data=bytes(account.data_hash),
        kind=AtomKind.LIST,
    )
    counter_atom = Atom(
        data=int_to_bytes(account.counter),
        next_id=data_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    code_atom = Atom(
        data=bytes(account.code_hash),
        next_id=counter_atom.object_id(),
        kind=AtomKind.LIST,
    )
    channels_atom = Atom(
        data=bytes(account.channels_hash),
        next_id=code_atom.object_id(),
        kind=AtomKind.LIST,
    )
    balance_atom = Atom(
        data=int_to_bytes(account.balance),
        next_id=channels_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    type_atom = Atom(
        data=b"account",
        next_id=balance_atom.object_id(),
        kind=AtomKind.SYMBOL,
    )

    atoms = [data_atom, counter_atom, code_atom, channels_atom, balance_atom, type_atom]
    return type_atom.object_id(), list(atoms)
