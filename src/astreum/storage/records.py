from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

from astreum.expression import Expr
from astreum.storage.put.cold.insert import put_expr_in_cold_storage
from astreum.storage.get.single.cold.get import get_expr_from_cold_storage
from astreum.storage.get.list.cold import iter_exprs_in_cold_storage

if TYPE_CHECKING:
    from astreum.node import Node


def _records_dir(node: "Node") -> Path | None:
    atoms_dir = node.config.get("cold_storage_path")
    if not atoms_dir:
        return None
    return Path(atoms_dir) / "records"


def write_record_slots(node: "Node", record_hash: bytes, slot_ids: list[bytes]) -> bool:
    """Write one record's slot list into the records LSM table.

    key = ``record_hash`` (value hash), value = concat of the 32-byte slot
    data ids in sequence order.  Reuses the expr cold-store machinery
    (``put_expr_in_cold_storage``) with the ``records/`` subtree as its base
    dir, so collate/merge are handled identically.
    """
    records_dir = _records_dir(node)
    if records_dir is None:
        return False

    value = b"".join(slot_ids)
    store = Expr("bytes", value=value)
    return put_expr_in_cold_storage(
        node,
        store,
        base_dir=records_dir,
        size_attr="records_level_0_size",
        key=record_hash,
    )


def get_record_value(node: "Node", record_hash: bytes) -> bytes | None:
    """Return the raw concat value blob for a record, or None."""
    records_dir = _records_dir(node)
    if records_dir is None:
        return None
    expr = get_expr_from_cold_storage(node, record_hash, base_dir=records_dir)
    if expr is None:
        return None
    return expr.value


def iter_record_hashes(node: "Node") -> Iterator[bytes]:
    """Yield record hashes (keys) in the records table, one at a time."""
    records_dir = _records_dir(node)
    if records_dir is None:
        return
    yield from iter_exprs_in_cold_storage(node, base_dir=records_dir)
