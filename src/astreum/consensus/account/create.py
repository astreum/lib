from __future__ import annotations

from ...storage.models.atom import ZERO32
from ...storage.models.trie import Trie
from .atomize import atomize_account
from .model import Account


def create_account(
    balance: int = 0,
    data_hash: bytes = ZERO32,
    channels_hash: bytes = ZERO32,
    code_hash: bytes = ZERO32,
    counter: int = 0,
) -> Account:
    account = Account(
        balance=int(balance),
        code_hash=bytes(code_hash),
        counter=int(counter),
        data_hash=bytes(data_hash),
        channels_hash=bytes(channels_hash),
        data=Trie(root_hash=bytes(data_hash)),
        channels=Trie(root_hash=bytes(channels_hash)),
    )
    atom_hash, atoms = atomize_account(account)
    account.atom_hash = atom_hash
    account.atoms = atoms
    return account
