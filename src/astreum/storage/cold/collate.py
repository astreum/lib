
from __future__ import annotations

import os
from pathlib import Path


def _cleanup_temp(*paths: Path) -> None:
    for path in paths:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass


def _fsync_dir(path: Path) -> None:
    try:
        dir_fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)


# index structure
# first 64 bytes is the number of items in the index
# follwed by a concat of the items in the order of the atom hash
# atom hash(32 bytes) | position(64 bytes) | size(64 bytes)

# the collated file structure
# concat of all the binaries


def _next_collated_number(l1_path: Path) -> int:
    max_number = -1
    for path in l1_path.glob("*_index"):
        prefix = path.name.split("_", 1)[0]
        if prefix.isdigit():
            max_number = max(max_number, int(prefix))
    return max_number + 1


def collate_atoms(atoms_dir: str | Path) -> bool:
    level_0_path = Path(atoms_dir) / "level_0"
    level_1_path = Path(atoms_dir) / "level_1"

    if not level_0_path.exists() or not level_0_path.is_dir():
        return False

    try:
        level_1_path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False

    entries = []
    for atom_path in level_0_path.glob("*.bin"):
        atom_hex = atom_path.stem
        try:
            atom_hash = bytes.fromhex(atom_hex)
        except ValueError:
            return False
        if len(atom_hash) != 32:
            return False
        try:
            atom_size = atom_path.stat().st_size
        except OSError:
            return False
        entries.append((atom_hash, atom_path, atom_size))

    if not entries:
        return False

    entries.sort(key=lambda item: item[0])

    atom_position = 0
    index_entries = []
    for atom_hash, atom_path, atom_size in entries:
        index_entries.append((atom_hash, atom_position, atom_size, atom_path))
        atom_position += atom_size

    file_number = _next_collated_number(level_1_path)
    index_path = level_1_path / f"{file_number}_index"
    data_path = level_1_path / f"{file_number}_data"
    index_tmp_path = level_1_path / f"{file_number}_index.tmp"
    data_tmp_path = level_1_path / f"{file_number}_data.tmp"

    try:
        with index_tmp_path.open("wb") as index_file:
            index_file.write(len(index_entries).to_bytes(64, "big", signed=False))
            for atom_hash, position, size, _ in index_entries:
                index_file.write(atom_hash)
                index_file.write(position.to_bytes(64, "big", signed=False))
                index_file.write(size.to_bytes(64, "big", signed=False))
            index_file.flush()
            os.fsync(index_file.fileno())
    except (OSError, OverflowError):
        _cleanup_temp(index_tmp_path, data_tmp_path)
        return False

    try:
        with data_tmp_path.open("wb") as data_file:
            for _, _, _, atom_path in index_entries:
                data_file.write(atom_path.read_bytes())
            data_file.flush()
            os.fsync(data_file.fileno())
    except OSError:
        _cleanup_temp(index_tmp_path, data_tmp_path)
        return False

    try:
        os.replace(data_tmp_path, data_path)
        os.replace(index_tmp_path, index_path)
        _fsync_dir(level_1_path)
    except OSError:
        _cleanup_temp(index_tmp_path, data_tmp_path)
        return False

    for _, _, _, atom_path in index_entries:
        try:
            atom_path.unlink()
        except OSError:
            return False

    return True
