from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

from astreum.expression import Expr, get_expr_tag, get_expr_value, resolve_list_exprs
from astreum.storage.put.cold.insert import put_expr_in_cold_storage
from astreum.storage.get.single.cold.get import get_expr_from_cold_storage
from astreum.storage.get.single.local import get_expr_from_local_storage
from astreum.storage.get.list.cold import iter_exprs_in_cold_storage
from astreum.storage.radix import RadixTree, get_from_radix_tree

if TYPE_CHECKING:
    from astreum.node import Node


def _records_dir(node: "Node") -> Path | None:
    store_dir = node.config.get("cold_storage_path")
    if not store_dir:
        return None
    return Path(store_dir) / "records"


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


def parse_slot(node: "Node", value: Any) -> tuple[bytes, int] | None:
    """Classify a storage-trie value as a ``StorageSlot``.

    A slot is ``Link(head_hash=record_hash, tail=Int(sequence))``.  Anything
    else (a record header, malformed data, an unresolved hash) is not a slot.
    """
    if value is None or getattr(value, "_tag", None) != "link":
        return None
    if value._head_hash is None:
        return None
    tail = value._tail
    if tail is None and value._tail_hash is not None:
        tail = get_expr_from_local_storage(node, value._tail_hash)
    if tail is None:
        return None
    try:
        if get_expr_tag(tail, node) != "int":
            return None
        return value._head_hash, get_expr_value(tail, node)
    except (AttributeError, TypeError, ValueError):
        return None


def parse_record_new_count(node: "Node", value: Any) -> int | None:
    """Extract ``new_count`` from a ``StorageRecord`` header expr.

    The header is the value stored in the storage trie at the record's key
    (the block's expr hash).  Mirrors ``StorageRecord.from_storage`` layout:
    6 or 7 elements with ``new_count`` at index 4 or 5.
    """
    if value is None or getattr(value, "_tag", None) != "link":
        return None
    nodes, missed = resolve_list_exprs(node, value)
    if missed or len(nodes) not in (6, 7):
        return None
    mint_idx = 3
    count_idx = 5 if len(nodes) == 7 else 4
    try:
        if get_expr_tag(nodes[mint_idx], node) != "int":
            return None
        if get_expr_tag(nodes[count_idx], node) != "int":
            return None
        return get_expr_value(nodes[count_idx], node)
    except (AttributeError, TypeError, ValueError):
        return None


def collect_record_slots(
    node: "Node",
    tree: RadixTree,
    block_expr: Any,
    record_hash: bytes,
    new_count: int,
) -> list[bytes]:
    """Walk a block expr, deriving its record's slot list.

    For each descendant link-node hash the storage trie is consulted:

    * a ``StorageSlot`` whose ``record_hash`` matches *record_hash* fills
      its position (``sequence``) in a ``new_count * 32`` zero-filled concat
      and its subtree is still walked (descendants are also this record's
      slots);
    * a slot or record belonging to a different record short-circuits the
      subtree;
    * unregistered exprs are walked through.

    Returns the concat as 32-byte slot ids, zeros marking released or
    unavailable positions (the claim worker treats ``ZERO32`` as unclaimable).
    """
    concat = bytearray(new_count * 32)
    seen: set[bytes] = set()
    stack: list[Any] = [block_expr]

    while stack:
        expr = stack.pop()
        if expr is None or getattr(expr, "_tag", None) != "link":
            continue
        h = expr.hash()
        if h in seen:
            continue
        seen.add(h)

        if h != record_hash:
            value = get_from_radix_tree(tree, node, h)
            if value is not None:
                slot = parse_slot(node, value)
                if slot is None:
                    continue
                slot_record, sequence = slot
                if slot_record != record_hash:
                    continue
                if 0 <= sequence < new_count:
                    offset = sequence * 32
                    concat[offset : offset + 32] = h

        if expr._head is not None:
            stack.append(expr._head)
        if expr._tail is not None:
            stack.append(expr._tail)

    return [bytes(concat[i : i + 32]) for i in range(0, len(concat), 32)]


def fetch_and_store_record(
    node: "Node",
    record_hash: bytes,
    tree: RadixTree,
    new_count: int,
) -> bool:
    """Fetch a record's data expr (lazily, one sub-expr at a time), write every
    expr to cold storage, and write its records-table entry.

    Trie semantics mirror :func:`collect_record_slots` exactly: slot for this
    record fills its position and the subtree is still walked; slot for
    another record or a non-slot trie value skips the subtree; no trie value
    walks through.  Children are fetched via :func:`get_expr` as encountered
    and each fetched expr is cold-written immediately (which also sidesteps
    hot-storage LRU eviction between fetch and write).  ``write_record_slots``
    only runs once the walk completes, so a failed walk leaves the records
    table untouched.
    """
    from astreum.storage.get.single.main import get_expr

    root = get_expr(node, record_hash)  # hot -> cold -> network (indexed provider)
    if root is None:
        return False
    put_expr_in_cold_storage(node, root)

    concat = bytearray(new_count * 32)
    seen: set[bytes] = set()
    stack: list[Any] = [root]

    while stack:
        expr = stack.pop()
        if expr is None or getattr(expr, "_tag", None) != "link":
            continue
        h = expr.hash()
        if h in seen:
            continue
        seen.add(h)

        if h != record_hash:
            value = get_from_radix_tree(tree, node, h)
            if value is not None:
                slot = parse_slot(node, value)
                if slot is None:
                    continue
                slot_record, sequence = slot
                if slot_record != record_hash:
                    continue
                if 0 <= sequence < new_count:
                    concat[sequence * 32 : sequence * 32 + 32] = h

        put_expr_in_cold_storage(node, expr)

        # Lazy resolution: one network fetch per child, as encountered.
        if expr._head is None and expr._head_hash is not None:
            resolved = get_expr(node, expr._head_hash)
            if resolved is not None:
                expr._head = resolved
                expr._head_hash = None
        if expr._tail is None and expr._tail_hash is not None:
            resolved = get_expr(node, expr._tail_hash)
            if resolved is not None:
                expr._tail = resolved
                expr._tail_hash = None
        if expr._head is not None:
            stack.append(expr._head)
        if expr._tail is not None:
            stack.append(expr._tail)

    slot_ids = [bytes(concat[i : i + 32]) for i in range(0, len(concat), 32)]
    return write_record_slots(node, record_hash, slot_ids)
