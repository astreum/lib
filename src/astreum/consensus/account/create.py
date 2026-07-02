from __future__ import annotations

from ...machine.models.expression import ZERO32
from ...storage.models.trie import Trie
from .model import Account


def create_account(
    balance: int = 0,
    data_hash: bytes = ZERO32,
    channels_hash: bytes = ZERO32,
    code_hash: bytes = ZERO32,
    counter: int = 0,
) -> Account:
    return Account(
        balance=balance,
        code_hash=code_hash,
        counter=counter,
        data_hash=data_hash,
        channels_hash=channels_hash,
        data=Trie(root_hash=data_hash),
        channels=Trie(root_hash=channels_hash),
    )
