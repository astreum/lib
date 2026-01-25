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

from .collate import _next_collated_number


def _iter_index_entries(index_path: Path):
    with index_path.open("rb") as index_file:
        count_bytes = index_file.read(64)
        if len(count_bytes) != 64:
            raise ValueError("Invalid index header")
        count = int.from_bytes(count_bytes, "big", signed=False)
        for _ in range(count):
            atom_hash = index_file.read(32)
            pos_bytes = index_file.read(64)
            size_bytes = index_file.read(64)
            if len(atom_hash) != 32 or len(pos_bytes) != 64 or len(size_bytes) != 64:
                raise ValueError("Invalid index entry")
            position = int.from_bytes(pos_bytes, "big", signed=False)
            size = int.from_bytes(size_bytes, "big", signed=False)
            yield atom_hash, position, size


def merge_atoms(atoms_dir: str | Path, level: int) -> bool:
    current_level_path = Path(atoms_dir) / f"level_{level}"
    next_level_path = Path(atoms_dir) / f"level_{level + 1}"

    if not current_level_path.exists() or not current_level_path.is_dir():
        return False

    try:
        next_level_path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False

    merged_index: dict[bytes, tuple[int, int, int]] = {}

    for index_path in current_level_path.glob("*_index"):
        prefix = index_path.name.split("_", 1)[0]
        if not prefix.isdigit():
            return False
        file_number = int(prefix)
        try:
            for atom_hash, pos, size in _iter_index_entries(index_path):
                merged_index[atom_hash] = (file_number, pos, size)
        except (OSError, ValueError, OverflowError):
            return False

    if not merged_index:
        return False

    sorted_keys = sorted(merged_index.keys())

    new_file_number = _next_collated_number(next_level_path)
    index_path = next_level_path / f"{new_file_number}_index"
    data_path = next_level_path / f"{new_file_number}_data"
    index_tmp_path = next_level_path / f"{new_file_number}_index.tmp"
    data_tmp_path = next_level_path / f"{new_file_number}_data.tmp"

    try:
        with index_tmp_path.open("wb") as index_file:
            index_file.write(len(sorted_keys).to_bytes(64, "big", signed=False))
            new_position = 0
            for atom_hash in sorted_keys:
                _, _, size = merged_index[atom_hash]
                index_file.write(atom_hash)
                index_file.write(new_position.to_bytes(64, "big", signed=False))
                index_file.write(size.to_bytes(64, "big", signed=False))
                new_position += size
            index_file.flush()
            os.fsync(index_file.fileno())
    except (OSError, OverflowError):
        _cleanup_temp(index_tmp_path, data_tmp_path)
        return False

    source_files: dict[int, object] = {}
    try:
        with data_tmp_path.open("wb") as data_file:
            for atom_hash in sorted_keys:
                file_number, pos, size = merged_index[atom_hash]
                source_file = source_files.get(file_number)
                if source_file is None:
                    source_path = current_level_path / f"{file_number}_data"
                    source_file = source_path.open("rb")
                    source_files[file_number] = source_file
                source_file.seek(pos)
                chunk = source_file.read(size)
                if len(chunk) != size:
                    raise ValueError("truncated atom data")
                data_file.write(chunk)
            data_file.flush()
            os.fsync(data_file.fileno())
    except (OSError, ValueError):
        _cleanup_temp(index_tmp_path, data_tmp_path)
        return False
    finally:
        for handle in source_files.values():
            try:
                handle.close()
            except OSError:
                pass
    try:
        os.replace(data_tmp_path, data_path)
        os.replace(index_tmp_path, index_path)
        _fsync_dir(next_level_path)
    except OSError:
        _cleanup_temp(index_tmp_path, data_tmp_path)
        return False
    for entry in current_level_path.iterdir():
        try:
            if entry.is_file():
                entry.unlink()
        except OSError:
            return False

    return True
