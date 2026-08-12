from __future__ import annotations

from pathlib import Path
from typing import Any

from astreum.storage.put.cold.collate import collate_exprs
from astreum.storage.put.cold.merge import merge_exprs
from astreum.expression.encoding import encode_expr_to_bytes


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


def put_expr_in_cold_storage(node: Any, expr: "Expr") -> bool:
    """Write an Expr into cold storage with automatic collation and merging.

    Stores the expression bytes to ``level_0`` under its content hash.
    If ``level_0`` exceeds ``cold_storage_base_size``, triggers a
    collation step that packs entries into higher levels.  Higher
    levels that exceed their size limit (``base_size × 10^level``)
    are merged recursively.

    Link children are stored before their parent to guarantee that
    all dependencies are on disk before the parent reference.

    Args:
        node: A Node instance providing config and storage access.
        expr: The expression to persist.

    Returns:
        True on success, False if storage is misconfigured or an
        I/O error occurs.
    """
    # Descend into Link children first so they're stored before the parent
    if expr.base == "link":
        if expr._head is not None:
            put_expr_in_cold_storage(node, expr._head)
        if expr._tail is not None:
            put_expr_in_cold_storage(node, expr._tail)
        # For builtin composites (int, str, float), the encoded value must be stored
        # as a separate bytes expression so head_hash can be resolved later.
        if expr._head is None and expr.value is not None and expr._tail is not None and expr._tail.base == "symbol":
            from astreum.expression.expr import TYPE_SYMBOLS, TAG_BYTE_ENCODINGS, Expr
            type_name = expr._tail.value
            if type_name in TYPE_SYMBOLS:
                encoder = TAG_BYTE_ENCODINGS.get(type_name)
                if encoder is not None:
                    encoded = encoder(expr.value)
                    value_expr = Expr("bytes", value=encoded)
                    put_expr_in_cold_storage(node, value_expr)

    expr_id = expr.hash()
    expr_bytes = encode_expr_to_bytes(expr)

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
