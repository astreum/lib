from __future__ import annotations

import secrets

from astreum.communication.util import xor_distance
from astreum.storage.models.atom import Atom, AtomKind, bytes_list_to_atoms


def generate_nearest_atom(
    peer_1_id: bytes,
    peer_2_id: bytes,
    *,
    max_attempts: int = 1000,
) -> Atom:
    """Return an atom whose ID is closer to peer_2_id than peer_1_id."""
    for _ in range(max_attempts):
        atom = Atom(data=secrets.token_bytes(32), kind=AtomKind.BYTES)
        atom_id = atom.object_id()
        if xor_distance(atom_id, peer_2_id) < xor_distance(atom_id, peer_1_id):
            return atom

    raise RuntimeError("Could not generate an atom closer to peer_2_id")


def generate_nearest_atom_list(
    peer_1_id: bytes,
    peer_2_id: bytes,
    list_size: int,
    *,
    max_attempts: int = 1000,
) -> list[Atom]:
    """Return a list of atoms whose head is closer to peer_2_id than peer_1_id."""
    if list_size <= 0:
        raise ValueError("list_size must be greater than 0")

    payloads = [secrets.token_bytes(32) for _ in range(list_size)]
    _, atoms = bytes_list_to_atoms(payloads)
    head_atom = atoms[0]

    for _ in range(max_attempts):
        head_atom.data = secrets.token_bytes(32)
        head_atom.size = len(head_atom.data)
        atom_id = head_atom.object_id()
        if xor_distance(atom_id, peer_2_id) < xor_distance(atom_id, peer_1_id):
            return atoms

    raise RuntimeError("Could not generate an atom list closer to peer_2_id")
