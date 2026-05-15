from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ...storage.models.atom import Atom, ZERO32
from ...storage.models.trie import Trie


@dataclass
class Account:
    balance: int
    code_hash: bytes
    counter: int
    data_hash: bytes
    channels_hash: bytes
    data: Trie
    channels: Trie
    atom_hash: bytes = ZERO32
    atoms: List[Atom] = field(default_factory=list)

    def clone(self) -> "Account":
        return Account(
            balance=int(self.balance),
            code_hash=bytes(self.code_hash),
            counter=int(self.counter),
            data_hash=bytes(self.data_hash),
            channels_hash=bytes(self.channels_hash),
            data=self.data.clone(),
            channels=self.channels.clone(),
            atom_hash=bytes(self.atom_hash),
            atoms=list(self.atoms),
        )
