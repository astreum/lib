from __future__ import annotations

from typing import Any, List, Optional, Tuple

from ...block.rate import calculate_storage_fee
from ....machine.models.expression import Expr, resolve_inner_exprs, resolve_list_exprs
from ....machine.models.expression import ZERO32
from ....validation.constants import BURN_ADDRESS
from ..model import Transaction
from .model import StorageRecord, StorageSlot

def generate_initial_storage_record(
    node: Any,
    block: object,
    expr: Expr,
    temp_exprs: dict[bytes, Expr] | None = None,
) -> Tuple[StorageRecord, dict[bytes, StorageSlot], List[bytes], int] | None:
    """
    Walk expr tree, slot new sub-exprs not yet registered in burn account data.
    Returns (StorageRecord, slot_map, found_exprs, storage_fee) for a fresh
    expr, or None if already registered.  slot_map maps each new sub-expr's
    hash to its StorageSlot.  found_exprs contains hashes of sub-exprs already
    in burn data (shared refs).
    """
    burn_account = block.accounts.get_account(BURN_ADDRESS, node)
    burn_data = burn_account.data

    root_hash = expr.hash()
    existing = burn_data.get(node, root_hash)
    if existing is not None:
        return None  # Already registered — nothing to do

    record_hash = root_hash
    slot_map: dict[bytes, StorageSlot] = {}
    found_exprs: list[bytes] = []
    total_new_size = 0

    def _slot_if_new(sub_expr: Expr) -> None:
        nonlocal total_new_size
        h = sub_expr.hash()
        if burn_data.get(node, h) is not None:
            found_exprs.append(h)
            return  # Shared reference — skip entire subtree
        slot_map[h] = StorageSlot(
            record_hash=record_hash,
            sequence=len(slot_map),
        )
        total_new_size += sub_expr.size()
        if isinstance(sub_expr, Expr.Link):
            if sub_expr.head is not None:
                _slot_if_new(sub_expr.head)
            if sub_expr.tail is not None:
                _slot_if_new(sub_expr.tail)
            if sub_expr.head_hash is not None and sub_expr.head is None:
                ptr = sub_expr.head_hash
                if burn_data.get(node, ptr) is not None:
                    return
                if temp_exprs is not None:
                    target = temp_exprs.get(ptr)
                    if target is not None and isinstance(target, Expr.Link):
                        if target.head is not None:
                            _slot_if_new(target.head)
                        if target.tail is not None:
                            _slot_if_new(target.tail)

    if isinstance(expr, Expr.Link):
        if expr.head is not None:
            _slot_if_new(expr.head)
        if expr.tail is not None:
            _slot_if_new(expr.tail)

    storage_fee = calculate_storage_fee(block, total_new_size)
    record = StorageRecord(
        creation_block_hash=block.previous_block_hash,
        last_payment_block_hash=block.previous_block_hash,
        last_payment_winner=ZERO32,
        new_size=total_new_size,
        new_count=len(slot_map),
    )
    return record, slot_map, found_exprs, storage_fee


def build_storage_contract_record(
    *,
    creation_previous_block_hash: bytes,
    new_size: int,
    new_count: int,
) -> tuple[bytes, list[Expr]]:
    record = StorageRecord(
        creation_block_hash=creation_previous_block_hash,
        last_payment_block_hash=creation_previous_block_hash,
        last_payment_winner=ZERO32,
        new_size=new_size,
        new_count=new_count,
    )
    return record.expr().hash(), [record.expr()]


def handle_storage_initial_contract(
    *,
    node: Any,
    block: object,
    transaction: Transaction,
    sender_account: Any,
    burn_account: Any,
    expr_list_id: bytes,
    current_fees: int,
) -> int | None:
    """Handle a storage-initial contract transaction and return charged storage fee."""
    try:
        existing_record = burn_account.data.get(node, expr_list_id)
        if existing_record is not None:
            return None

        list_expr = node.get_expr_list(expr_list_id)
        if list_expr is None:
            return None
        list_items, _ = resolve_list_exprs(node, list_expr)
        total_bytes = sum(item.size() for item in list_items)
        number_of_exprs = len(list_items)

        storage_cost = calculate_storage_fee(block, total_bytes)
        if sender_account.balance < current_fees + storage_cost:
            return None

        record_value, record_exprs = build_storage_contract_record(
            creation_previous_block_hash=block.previous_block_hash,
            new_size=total_bytes,
            new_count=number_of_exprs,
        )

        burn_account.data.put(node, expr_list_id, record_value)
        burn_account.data_hash = burn_account.data.root_hash
        burn_account.balance += storage_cost
        sender_account.balance -= storage_cost

        block.pending_exprs.extend(record_exprs)
        return storage_cost
    except Exception:
        return None
