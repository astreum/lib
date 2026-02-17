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
