from __future__ import annotations

from typing import Any

from ...block.iaar import calculate_storage_fee
from ...machine.models.expression import Expr, resolve_inner_exprs, resolve_list_exprs
from ....machine.models.expression import ZERO32
from ....utils.integer import int_to_bytes
from ..model import Transaction
from .model import StorageRecord

ATOM_OVERHEAD_BYTES = 33  # next_id (32) + kind (1)


def build_storage_contract_record(
    *,
    owner_public_key: bytes,
    creation_previous_block_hash: bytes,
    total_bytes: int,
    number_of_atoms: int,
) -> tuple[bytes, list[Expr]]:
    record = StorageRecord(
        owner_public_key=owner_public_key,
        creation_block_hash=creation_previous_block_hash,
        last_payment_block_hash=creation_previous_block_hash,
        last_payment_winner=ZERO32,
        total_bytes=total_bytes,
        number_of_atoms=number_of_atoms,
    )
    return record.expr().hash(), [record.expr()]


def handle_storage_initial_contract(
    *,
    node: Any,
    block: object,
    transaction: Transaction,
    sender_account: Any,
    burn_account: Any,
    atom_list_id: bytes,
    current_fees: int,
) -> int | None:
    """Handle a storage-initial contract transaction and return charged storage fee."""
    try:
        existing_record = burn_account.data.get(node, atom_list_id)
        if existing_record is not None:
            return None

        list_expr = node.get_expr_list(atom_list_id)
        if list_expr is None:
            return None
        list_items, _ = resolve_list_exprs(node, list_expr)
        total_bytes = sum(item.size() for item in list_items)
        number_of_atoms = len(list_items)

        storage_cost = calculate_storage_fee(block, total_bytes)
        if sender_account.balance < current_fees + storage_cost:
            return None

        record_value, record_atoms = build_storage_contract_record(
            owner_public_key=transaction.sender,
            creation_previous_block_hash=block.previous_block_hash,
            total_bytes=total_bytes,
            number_of_atoms=number_of_atoms,
        )

        burn_account.data.put(node, atom_list_id, record_value)
        burn_account.data_hash = burn_account.data.root_hash
        burn_account.balance += storage_cost
        sender_account.balance -= storage_cost

        block.pending_exprs.extend(record_atoms)
        return storage_cost
    except Exception:
        return None
