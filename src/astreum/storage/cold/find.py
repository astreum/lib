from __future__ import annotations

from pathlib import Path
from typing import Optional


def find_atom_in_index(index_filepath: str | Path, key: bytes) -> Optional[tuple[bytes, bytes]]:
    if len(key) != 32:
        return None

    index_path = Path(index_filepath)
    try:
        with index_path.open("rb") as index_file:
            count_bytes = index_file.read(64)
            if len(count_bytes) != 64:
                return None
            count = int.from_bytes(count_bytes, "big", signed=False)
            if count == 0:
                return None
            entry_size = 32 + 64 + 64
            left = 0
            right = count - 1
            while left <= right:
                mid = (left + right) // 2
                index_file.seek(64 + (mid * entry_size))
                atom_hash = index_file.read(32)
                pos_bytes = index_file.read(64)
                size_bytes = index_file.read(64)
                if len(atom_hash) != 32 or len(pos_bytes) != 64 or len(size_bytes) != 64:
                    return None
                if atom_hash == key:
                    return pos_bytes, size_bytes
                if atom_hash < key:
                    left = mid + 1
                else:
                    right = mid - 1
    except OSError:
        return None
    return None
