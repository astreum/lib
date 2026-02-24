from typing import List

from ...storage.models.atom import Atom


OBJECT_FOUND_ATOM_PAYLOAD = 1
OBJECT_FOUND_LIST_PAYLOAD = 2


def encode_object_found_atom_payload(atom: Atom) -> bytes:
    return bytes([OBJECT_FOUND_ATOM_PAYLOAD]) + atom.to_bytes()


def encode_object_found_list_payload(atoms: List[Atom]) -> bytes:
    parts = [bytes([OBJECT_FOUND_LIST_PAYLOAD])]
    for atom in atoms:
        atom_bytes = atom.to_bytes()
        parts.append(len(atom_bytes).to_bytes(4, "big", signed=False))
        parts.append(atom_bytes)
    return b"".join(parts)


def decode_object_found_list_payload(payload: bytes) -> List[Atom]:
    atoms: List[Atom] = []
    offset = 0
    while offset < len(payload):
        if len(payload) - offset < 4:
            raise ValueError("truncated atom length")
        atom_len = int.from_bytes(payload[offset : offset + 4], "big", signed=False)
        offset += 4
        if atom_len <= 0:
            raise ValueError("invalid atom length")
        end = offset + atom_len
        if end > len(payload):
            raise ValueError("truncated atom payload")
        atoms.append(Atom.from_bytes(payload[offset:end]))
        offset = end
    return atoms
