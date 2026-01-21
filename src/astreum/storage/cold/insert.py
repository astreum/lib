from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models.atom import Atom
from .collate import collate_atoms
from .merge import merge_atoms

LEVEL_0_SIZE_LIMIT = 1_000_000


def _level_size(level_path: Path) -> int | None:
    total = 0
    for entry in level_path.iterdir():
        try:
            if entry.is_file():
                total += entry.stat().st_size
        except OSError:
            return None
    return total

def insert_atom_into_cold_storage(node: Any, atom: Atom) -> bool:
    atom_hash = atom.object_id()
    atom_bytes = atom.to_bytes()

    atoms_dir = node.config["cold_storage_path"]
    level_0_path = Path(atoms_dir) / "level_0"
    try:
        level_0_path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False

    atom_path = level_0_path / f"{atom_hash.hex().upper()}.bin"
    try:
        atom_path.write_bytes(atom_bytes)
    except OSError:
        return False

    node.cold_storage_level_0_size += len(atom_bytes)

    if node.cold_storage_level_0_size > LEVEL_0_SIZE_LIMIT:
        if not collate_atoms(Path(atoms_dir)):
            return False

        level = 1
        while True:
            level_path = Path(atoms_dir) / f"level_{level}"
            if not level_path.exists() or not level_path.is_dir():
                break

            level_bytes = _level_size(level_path)
            if level_bytes is None:
                return False
            level_limit = LEVEL_0_SIZE_LIMIT * (10 ** level)
            if level_bytes > level_limit:
                if not merge_atoms(Path(atoms_dir), level):
                    return False

            level += 1

    return True
