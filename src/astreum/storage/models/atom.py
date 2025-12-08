

from enum import IntEnum
from typing import List, Optional, Tuple

from blake3 import blake3

ZERO32 = b"\x00"*32

def u64_le(n: int) -> bytes:
    return int(n).to_bytes(8, "little", signed=False)

def hash_bytes(b: bytes) -> bytes:
    return blake3(b).digest()

class AtomKind(IntEnum):
    SYMBOL = 0
    BYTES = 1
    LIST = 2


class Atom:
    data: bytes
    kind: AtomKind
    next_id: bytes
    size: int
    
    def __init__(self, data: bytes, kind: AtomKind, next_id: bytes = ZERO32):
        self.data = data
        self.kind = kind
        self.next_id = next_id
        self.size = len(data)
        

    def generate_id(self) -> bytes:
        """Compute the object id using this atom's metadata."""
        kind_bytes = int(self.kind).to_bytes(1, "little", signed=False)
        return blake3(
            kind_bytes + self.data_hash() + self.next_id + u64_le(self.size)
        ).digest()

    def data_hash(self) -> bytes:
        return hash_bytes(self.data)

    def object_id(self) -> bytes:
        return self.generate_id()

    @staticmethod
    def verify_metadata(
        object_id: bytes,
        size: int,
        next_hash: bytes,
        data_hash: bytes,
        kind: AtomKind,
    ) -> bool:
        kind_bytes = int(kind).to_bytes(1, "little", signed=False)
        expected = blake3(kind_bytes + data_hash + next_hash + u64_le(size)).digest()
        return object_id == expected

    def to_bytes(self) -> bytes:
        """Serialize as next-hash + kind byte + payload."""
        kind_byte = int(self.kind).to_bytes(1, "little", signed=False)
        return self.next_id + kind_byte + self.data

    @staticmethod
    def from_bytes(buf: bytes) -> "Atom":
        header_len = len(ZERO32)
        if len(buf) < header_len + 1:
            raise ValueError("buffer too short for Atom header")
        next_hash = buf[:header_len]
        kind_value = buf[header_len]
        data = buf[header_len + 1 :]
        try:
            kind = AtomKind(kind_value)
        except ValueError as exc:
            raise ValueError(f"unknown atom kind: {kind_value}") from exc
        return Atom(data=data, next_id=next_hash, kind=kind)

def bytes_list_to_atoms(values: List[bytes]) -> Tuple[bytes, List[Atom]]:
    """Build a forward-ordered linked list of atoms from byte payloads.

    Returns the head object's hash (ZERO32 if no values) and the atoms created.
    """
    next_hash = ZERO32
    atoms: List[Atom] = []

    for value in reversed(values):
        atom = Atom(data=bytes(value), next_id=next_hash, kind=AtomKind.BYTES)
        atoms.append(atom)
        next_hash = atom.object_id()

    atoms.reverse()
    return (next_hash if values else ZERO32), atoms


def get_atom_list_from_storage(self, root_hash: bytes) -> Optional[List["Atom"]]:
    """Follow the list chain starting at root_hash, returning atoms or None on gaps."""
    next_id: bytes = root_hash
    atom_list: List["Atom"] = []
    while next_id != ZERO32:
        elem = self.storage_get(key=next_id)
        if elem:
            atom_list.append(elem)
            next_id = elem.next_id
        else:
            return None
    return atom_list
