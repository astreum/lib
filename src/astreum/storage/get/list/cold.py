from __future__ import annotations

from pathlib import Path
from typing import Any

from astreum.storage.put.cold.merge import _iter_index_entries


def list_exprs_in_cold_storage(node: Any) -> list[bytes]:
    """Return the unique content hashes present in cold storage.

    Collects ``level_0/*.bin`` filename stems plus every ``level_N/*_index``
    entry (N >= 1) under ``node.config["cold_storage_path"]``.  Runs under
    ``cold_storage_lock`` so collate/merge (which delete source files) cannot
    race the listing.  Returns a deduplicated list of 32-byte expr ids.
    """
    atoms_dir = node.config.get("cold_storage_path")
    if not atoms_dir:
        return []

    ids: set[bytes] = set()
    with node.cold_storage_lock:
        root = Path(atoms_dir)
        level_0_path = root / "level_0"
        if level_0_path.exists() and level_0_path.is_dir():
            for expr_path in level_0_path.glob("*.bin"):
                try:
                    expr_id = bytes.fromhex(expr_path.stem)
                except ValueError:
                    continue
                if len(expr_id) == 32:
                    ids.add(expr_id)

        level = 1
        while True:
            level_path = root / f"level_{level}"
            if not level_path.exists() or not level_path.is_dir():
                break
            for index_path in level_path.glob("*_index"):
                prefix = index_path.name.split("_", 1)[0]
                if not prefix.isdigit():
                    continue
                try:
                    for expr_id, _pos, _size in _iter_index_entries(index_path):
                        ids.add(expr_id)
                except (OSError, ValueError, OverflowError):
                    continue
            level += 1

    return list(ids)