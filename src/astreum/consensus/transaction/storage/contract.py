from __future__ import annotations

from typing import Any

from ...block.iaar import calculate_storage_fee
from ....machine.models.expression import resolve_inner_exprs
from ....validation.models.receipt import Receipt
from .initial import ATOM_OVERHEAD_BYTES, build_storage_contract_record
from ..model import Transaction

TX_STORAGE_ATOM_COUNT = 11
RECEIPT_STORAGE_ATOM_COUNT = 7
TX_FIXED_PAYLOAD_BYTES = 197  # numeric fields + sender/recipient + body list head + signature + version + type
RECEIPT_FIXED_PAYLOAD_BASE_BYTES = 74  # tx hash + status + tx_fee + logs hash + version + type


def _int_be_len(value: int) -> int:
    v = int(value)
    if v == 0:
        return 1
    return (v.bit_length() + 7) // 8


def _receipt_total_bytes_for_storage_fee(*, storage_fee: int) -> int:
    payload_bytes = RECEIPT_FIXED_PAYLOAD_BASE_BYTES + _int_be_len(storage_fee)
    return (RECEIPT_STORAGE_ATOM_COUNT * ATOM_OVERHEAD_BYTES) + payload_bytes


def calculate_transaction_costs(*, block: object, transaction: Transaction) -> int:
    tx_total_bytes = (TX_STORAGE_ATOM_COUNT * ATOM_OVERHEAD_BYTES) + TX_FIXED_PAYLOAD_BYTES + len(transaction.data)
    tx_storage_cost = calculate_storage_fee(block, tx_total_bytes)
    total_storage_fee = tx_storage_cost
    receipt_storage_cost = 0

    # Receipt bytes include the storage-fee field, so compute the mandatory
    # receipt storage cost to a fixed point.
    for _ in range(8):
        receipt_total_bytes = _receipt_total_bytes_for_storage_fee(storage_fee=total_storage_fee)
        receipt_storage_cost = calculate_storage_fee(block, receipt_total_bytes)
        next_total_storage_fee = tx_storage_cost + receipt_storage_cost
        if next_total_storage_fee == total_storage_fee:
            break
        total_storage_fee = next_total_storage_fee

    return tx_storage_cost + receipt_storage_cost


def generate_transaction_storage_contract(
    *,
    node: Any,
    block: object,
    transaction_hash: bytes,
    transaction: Transaction,
    burn_account: Any,
) -> int:
    tx_exprs, _ = resolve_inner_exprs(node, transaction.expr())
    if not tx_exprs:
        return 0

    total_bytes = sum(expr.size() for expr in tx_exprs)
    number_of_atoms = len(tx_exprs)
    storage_cost = calculate_storage_fee(block, total_bytes)
    record_value, record_atoms = build_storage_contract_record(
        owner_public_key=transaction.sender,
        creation_previous_block_hash=block.previous_block_hash,
        total_bytes=total_bytes,
        number_of_atoms=number_of_atoms,
    )

    burn_account.data.put(node, transaction_hash, record_value)
    burn_account.data_hash = burn_account.data.root_hash
    block.pending_exprs.extend(record_atoms)
    return storage_cost


def generate_receipt_storage_contract(
    *,
    node: Any,
    block: object,
    burn_account: Any,
    receipt: Receipt,
    sender_public_key: bytes,
) -> int:
    receipt_id = receipt.expr().hash()
    receipt_exprs, _ = resolve_inner_exprs(node, receipt)
    receipt.atom_hash = receipt_id

    total_bytes = sum(expr.size() for expr in receipt_exprs)
    number_of_atoms = len(receipt_exprs)
    storage_cost = calculate_storage_fee(block, total_bytes)
    record_value, record_atoms = build_storage_contract_record(
        owner_public_key=sender_public_key,
        creation_previous_block_hash=block.previous_block_hash,
        total_bytes=total_bytes,
        number_of_atoms=number_of_atoms,
    )

    if burn_account.data.get(node, receipt_id) is None:
        burn_account.data.put(node, receipt_id, record_value)
        burn_account.data_hash = burn_account.data.root_hash
        block.pending_exprs.extend(record_atoms)
        return storage_cost
    return 0
