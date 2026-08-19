from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from astreum.storage.get.single.cold.find import find_expr_in_index
from astreum.expression.encoding import decode_expr_from_bytes


def get_expr_from_cold_storage(
    node: Any,
    expr_id: bytes,
    base_dir: str | Path | None = None,
) -> Optional["Expr"]:
    """Retrieve an Expr from cold storage by content hash.

    Searches ``level_0/*.bin`` first, then walks ``level_N`` (ascending)
    index files in reverse file order (highest number first, which holds the
    most recent data for a key). Returns the first hit, decoded from bytes.
    Runs under ``cold_storage_lock`` so collate/merge cannot remove source
    files mid-read.

    Args:
        node: A Node instance providing ``config`` and ``cold_storage_lock``.
        expr_id: The 32-byte content hash of the expression to retrieve.
        base_dir: Optional base directory override (e.g. the ``records/``
            subtree). Defaults to ``node.config["cold_storage_path"]``.

    Returns:
        The decoded Expr, or ``None`` if not found or the data is malformed.
    """
    from astreum.expression import Expr

    store_dir = base_dir if base_dir is not None else node.config["cold_storage_path"]
    if store_dir is None:
        return None
    with node.cold_storage_lock:
        level_0_path = Path(store_dir) / "level_0"
        if level_0_path.exists() and level_0_path.is_dir():
            key_hex = expr_id.hex().upper()
            expr_path = level_0_path / f"{key_hex}.bin"
            try:
                data = expr_path.read_bytes()
                return decode_expr_from_bytes(data)
            except FileNotFoundError:
                pass
            except (OSError, ValueError):
                return None

        level = 1
        while True:
            level_path = Path(store_dir) / f"level_{level}"
            if not level_path.exists() or not level_path.is_dir():
                break

            index_files: list[tuple[int, Path]] = []
            for index_path in level_path.glob("*_index"):
                prefix = index_path.name.split("_", 1)[0]
                if prefix.isdigit():
                    index_files.append((int(prefix), index_path))

            index_files.sort(key=lambda item: item[0], reverse=True)

            for file_number, index_path in index_files:
                result = find_expr_in_index(index_path, expr_id)
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
                    return decode_expr_from_bytes(data)
                except ValueError:
                    return None

            level += 1

        return None


def get_expr_list_from_cold_storage(node: Any, root_hash: bytes) -> Optional["Expr"]:
    """Resolve a link chain from cold storage, following tail hashes.

    Loads the expr at ``root_hash`` and walks the ``_tail`` links, replacing
    each unresolved ``_tail_hash`` with the loaded tail expr. Traversal stops
    at the first tail that is not present in cold storage, leaving that
    ``_tail_hash`` unresolved.

    Args:
        node: A Node instance providing ``config`` and ``cold_storage_lock``.
        root_hash: The 32-byte content hash of the list head.

    Returns:
        The partially-resolved list Expr, or ``None`` if the head is absent.
    """
    from astreum.expression import Expr, ZERO32

    expr = get_expr_from_cold_storage(node, root_hash)
    if expr is None:
        return None

    current = expr
    while current is not None and current._tag == "link":
        if current._tail_hash is not None:
            if current._tail_hash == ZERO32:
                current._tail = None
                current._tail_hash = None
            else:
                tail = get_expr_from_cold_storage(node, current._tail_hash)
                if tail is None:
                    break
                current._tail = tail
                current._tail_hash = None
        current = current._tail

    return expr


def get_expr_full_from_cold_storage(node: Any, root_hash: bytes) -> Optional["Expr"]:
    """Recursively resolve all inner hashes from cold storage.

    Loads the expr at ``root_hash`` and resolves every unresolved
    ``_head_hash``/``_tail_hash`` depth-first, replacing them with the loaded
    child exprs. Repeatedly re-scans each node until no new progress is made
    (i.e. the remaining hashes are absent from cold storage).

    Args:
        node: A Node instance providing ``config`` and ``cold_storage_lock``.
        root_hash: The 32-byte content hash of the root expression.

    Returns:
        The fully-resolved (as far as cold storage allows) Expr, or ``None``
        if the root is absent.
    """
    from astreum.expression import Expr

    expr = get_expr_from_cold_storage(node, root_hash)
    if expr is None:
        return None
    if expr._tag != "link":
        return expr

    def _resolve(e: Expr) -> Expr:
        changed = True
        while changed:
            changed = False
            if e._tag != "link":
                break
            if e._head is None and e._head_hash is not None:
                head = get_expr_from_cold_storage(node, e._head_hash)
                if head is not None:
                    e._head = _resolve(head)
                    e._head_hash = None
                    changed = True
            if e._tail is None and e._tail_hash is not None:
                tail = get_expr_from_cold_storage(node, e._tail_hash)
                if tail is not None:
                    e._tail = _resolve(tail)
                    e._tail_hash = None
                    changed = True
        return e

    return _resolve(expr)
