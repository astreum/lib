from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ..models.atom import Atom
from .find import find_atom_in_index


def get_atom_from_cold_storage(node: Any, atom_id: bytes) -> Optional[Atom]:
    atoms_dir = node.config["cold_storage_path"]
    if atoms_dir is None:
        return None
    with node.cold_storage_lock:
        level_0_path = Path(atoms_dir) / "level_0"
        if level_0_path.exists() and level_0_path.is_dir():
            key_hex = atom_id.hex().upper()
            atom_path = level_0_path / f"{key_hex}.bin"
            try:
                data = atom_path.read_bytes()
                return Atom.from_bytes(data)
            except FileNotFoundError:
                pass
            except (OSError, ValueError):
                return None

        level = 1
        while True:
            level_path = Path(atoms_dir) / f"level_{level}"
            if not level_path.exists() or not level_path.is_dir():
                break

            index_files: list[tuple[int, Path]] = []
            for index_path in level_path.glob("*_index"):
                prefix = index_path.name.split("_", 1)[0]
                if prefix.isdigit():
                    index_files.append((int(prefix), index_path))

            index_files.sort(key=lambda item: item[0], reverse=True)

            for file_number, index_path in index_files:
                result = find_atom_in_index(index_path, atom_id)
                if result is None:
                    continue
                pos_bytes, size_bytes = result
                position = int.from_bytes(pos_bytes, "big", signed=False)
                size = int.from_bytes(size_bytes, "big", signed=False)
                data_path = level_path / f"{file_number}_data"
                try:
                    with data_path.open("rb") as data_file:
                        data_file.seek(position)
                        data = data_file.read(size)
                except OSError:
                    return None
                if len(data) != size:
                    return None
                try:
                    return Atom.from_bytes(data)
                except ValueError:
                    return None

            level += 1

        return None
