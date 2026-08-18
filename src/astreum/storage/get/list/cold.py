from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from astreum.storage.put.cold.merge import _iter_index_entries


def iter_exprs_in_cold_storage(
    node: Any,
    base_dir: str | Path | None = None,
) -> Iterator[bytes]:
    """Yield the unique content hashes present in cold storage.

    Yields ids one at a time (``level_0/*.bin`` stems plus every
    ``level_N/*_index`` entry, N >= 1) under
    ``node.config["cold_storage_path"]`` (or ``base_dir`` when given).
    ``cold_storage_lock`` is held only per segment read, never across the
    whole scan, so collate/merge (which delete source files) cannot race the
    listing while block production cold reads are also happening.
    """
    atoms_dir = base_dir if base_dir is not None else node.config.get("cold_storage_path")
    if not atoms_dir:
        return

    root = Path(atoms_dir)

    level_0_path = root / "level_0"
    if level_0_path.exists() and level_0_path.is_dir():
        with node.cold_storage_lock:
            stems = [p.stem for p in level_0_path.glob("*.bin")]
        for stem in stems:
            try:
                expr_id = bytes.fromhex(stem)
            except ValueError:
                continue
            if len(expr_id) == 32:
                yield expr_id

    level = 1
    while True:
        level_path = root / f"level_{level}"
        if not level_path.exists() or not level_path.is_dir():
            break
        with node.cold_storage_lock:
            index_paths = sorted(
                (
                    (int(p.name.split("_", 1)[0]), p)
                    for p in level_path.glob("*_index")
                    if p.name.split("_", 1)[0].isdigit()
                ),
                key=lambda item: item[0],
            )
        for _file_number, index_path in index_paths:
            try:
                with node.cold_storage_lock:
                    entries = list(_iter_index_entries(index_path))
            except (OSError, ValueError, OverflowError):
                continue
            for expr_id, _pos, _size in entries:
                yield expr_id
        level += 1


def list_exprs_in_cold_storage(node: Any) -> list[bytes]:
    """Return the unique content hashes present in cold storage (legacy).

    Collects every id from ``iter_exprs_in_cold_storage`` into a set.  Prefer
    the generator for scans that should not buffer the whole set or hold the
    lock across the listing.
    """
    return list(dict.fromkeys(iter_exprs_in_cold_storage(node)))
