from __future__ import annotations

from pathlib import Path
from typing import Any

from .collate import collate_exprs
from .merge import merge_exprs


def _level_size(level_path: Path) -> int | None:
    total = 0
    for entry in level_path.iterdir():
        try:
            if entry.is_file():
                total += entry.stat().st_size
        except OSError:
            return None
    return total


def _level_limit(node: Any, level: int) -> int:
    try:
        base_limit = int(node.config["cold_storage_base_size"])
    except (TypeError, ValueError) as exc:
        raise ValueError("cold_storage_base_size must be an integer") from exc
    if base_limit <= 0:
        raise ValueError("cold_storage_base_size must be positive")
    return base_limit * (10 ** level)


def insert_expr_into_cold_storage(node: Any, expr: "Expr") -> bool:

    # Descend into Link children first so they're stored before the parent
    if expr._tag == "link":
        if expr._head is not None:
            insert_expr_into_cold_storage(node, expr._head)
        if expr._tail is not None:
            insert_expr_into_cold_storage(node, expr._tail)

    expr_id = expr.hash()
    expr_bytes = expr.to_bytes()

    atoms_dir = node.config["cold_storage_path"]
    if not atoms_dir:
        return False
    level_0_path = Path(atoms_dir) / "level_0"

    with node.cold_storage_lock:
        expr_path = level_0_path / f"{expr_id.hex().upper()}.bin"
        try:
            expr_path.write_bytes(expr_bytes)
        except OSError:
            return False

        node.cold_storage_level_0_size += len(expr_bytes)

        if node.cold_storage_level_0_size > node.config["cold_storage_base_size"]:
            if not collate_exprs(Path(atoms_dir)):
                return False
            node.cold_storage_level_0_size = 0

            level = 1
            while True:
                level_path = Path(atoms_dir) / f"level_{level}"
                if not level_path.exists() or not level_path.is_dir():
                    break

                level_bytes = _level_size(level_path)
                if level_bytes is None:
                    return False
                try:
                    level_limit = _level_limit(node, level)
                except ValueError:
                    return False
                if level_bytes > level_limit:
                    if not merge_exprs(Path(atoms_dir), level):
                        return False

                level += 1

    return True
