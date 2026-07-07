from __future__ import annotations

from typing import Any

from ...block.rate import calculate_storage_fee
from ....machine.models.expression import NIL, resolve_inner_exprs
from ....validation.models.receipt import Receipt
from ....storage.radix import get_from_radix_tree, put_in_radix_tree
from .initial import build_storage_contract_record
from ..model import Transaction


def _int_be_len(value: int) -> int:
    v = value
    if v == 0:
        return 1
    return (v.bit_length() + 7) // 8


def calculate_transaction_costs(*, block: object, transaction: Transaction) -> int:
    """Estimate mandatory storage cost using the Expr.size() model."""
    tx_total_bytes = transaction.expr().size()
    tx_storage_cost = calculate_storage_fee(block, tx_total_bytes)
    total_storage_fee = tx_storage_cost
    receipt_storage_cost = 0

    tx_fee = 1
    logs_expr = NIL

    # Receipt bytes include the storage-fee field, so converge to a fixed point.
    for _ in range(8):
        receipt_bytes = (
            _int_be_len(total_storage_fee)
            + _int_be_len(tx_fee)
            + logs_expr.size()
            + 7                                       # Symbol("receipt")
            + 10 * 32                                 # link overhead (10 Links × 32)
            + 1                                       # status byte
        )
        receipt_storage_cost = calculate_storage_fee(block, receipt_bytes)
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
    number_of_exprs = len(tx_exprs)
    storage_cost = calculate_storage_fee(block, total_bytes)
    record_value, record_exprs = build_storage_contract_record(
        creation_previous_block_hash=block.previous_block_hash,
        creation_height=block.height,
        new_size=total_bytes,
        new_count=number_of_exprs,
    )

    put_in_radix_tree(burn_account.data, node, transaction_hash, record_value)
    burn_account.data_hash = burn_account.data.root_hash
    block.pending_exprs.extend(record_exprs)
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
    receipt_exprs, _ = resolve_inner_exprs(node, receipt.expr())
    receipt.expr_id = receipt_id

    total_bytes = sum(expr.size() for expr in receipt_exprs)
    number_of_exprs = len(receipt_exprs)
    storage_cost = calculate_storage_fee(block, total_bytes)
    record_value, record_exprs = build_storage_contract_record(
        creation_previous_block_hash=block.previous_block_hash,
        creation_height=block.height,
        new_size=total_bytes,
        new_count=number_of_exprs,
    )

    if get_from_radix_tree(burn_account.data, node, receipt_id) is None:
        put_in_radix_tree(burn_account.data, node, receipt_id, record_value)
        burn_account.data_hash = burn_account.data.root_hash
        block.pending_exprs.extend(record_exprs)
        return storage_cost
    return 0
