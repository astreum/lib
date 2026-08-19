from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from astreum.storage.put.cold.merge import _iter_index_entries


def iter_exprs_in_cold_storage(
    node: Any,
    base_dir: str | Path | None = None,
) -> Iterator[bytes]:
    """Iterate over the content hashes stored in cold storage.

    Yields ids one at a time from ``level_0/*.bin`` filename stems followed by
    every ``level_N/*_index`` entry (N >= 1). The lock is held only for each
    segment read (never across the whole scan), so collate/merge — which
    delete source files — cannot race the listing while other cold reads are
    happening.

    Args:
        node: A Node instance providing ``config`` and ``cold_storage_lock``.
        base_dir: Optional base directory override (e.g. the ``records/``
            subtree). Defaults to ``node.config["cold_storage_path"]``.

    Yields:
        The 32-byte content hash of each stored expression.
    """
    store_dir = base_dir if base_dir is not None else node.config.get("cold_storage_path")
    if not store_dir:
        return

    root = Path(store_dir)

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
