from __future__ import annotations

from typing import Any

from ...storage.models.atom import Atom
from ...validation.models.receipt import Receipt
from .storage_initial import ATOM_OVERHEAD_BYTES, build_storage_contract_record
from .storage_initial import calculate_storage_cost
from .model import Transaction

TX_STORAGE_ATOM_COUNT = 10
RECEIPT_STORAGE_ATOM_COUNT = 6
TX_FIXED_PAYLOAD_BYTES = 196  # numeric fields + sender/recipient + body list head + signature + version + type
RECEIPT_FIXED_PAYLOAD_BYTES = 74  # tx hash + status + cost + logs hash + version + type


def calculate_transaction_costs(*, block: object, transaction: Transaction) -> int:
    tx_total_bytes = (TX_STORAGE_ATOM_COUNT * ATOM_OVERHEAD_BYTES) + TX_FIXED_PAYLOAD_BYTES + len(transaction.data)
    receipt_total_bytes = (RECEIPT_STORAGE_ATOM_COUNT * ATOM_OVERHEAD_BYTES) + RECEIPT_FIXED_PAYLOAD_BYTES
    tx_storage_cost = calculate_storage_cost(block=block, total_bytes=tx_total_bytes)
    receipt_storage_cost = calculate_storage_cost(block=block, total_bytes=receipt_total_bytes)
    return tx_storage_cost + receipt_storage_cost


def generate_transaction_storage_contract(
    *,
    node: Any,
    block: object,
    transaction_hash: bytes,
    transaction: Transaction,
    sender_account: Any,
    burn_account: Any,
) -> int:
    tx_atoms = Transaction.get_atoms(node, transaction_hash)
    if tx_atoms is None:
        return 0

    total_bytes = sum(len(atom.data) + ATOM_OVERHEAD_BYTES for atom in tx_atoms)
    number_of_atoms = len(tx_atoms)
    storage_cost = calculate_storage_cost(block=block, total_bytes=total_bytes)
    record_value, record_atoms = build_storage_contract_record(
        owner_public_key=transaction.sender,
        creation_previous_block_hash=block.previous_block_hash,
        total_bytes=total_bytes,
        number_of_atoms=number_of_atoms,
    )

    burn_account.data.put(node, transaction_hash, record_value)
    burn_account.data_hash = burn_account.data.root_hash
    sender_account.balance -= storage_cost
    burn_account.balance += storage_cost

    if not hasattr(block, "contract_atoms") or block.contract_atoms is None:
        block.contract_atoms = []
    block.contract_atoms.extend(record_atoms)
    return storage_cost


def generate_receipt_storage_contract(
    *,
    node: Any,
    block: object,
    sender_account: Any,
    burn_account: Any,
    receipt: Receipt,
    sender_public_key: bytes,
) -> int:
    receipt_id, receipt_atoms = receipt.atomize()
    receipt.atom_hash = receipt_id
    receipt.atoms = receipt_atoms

    total_bytes = sum(len(atom.data) + ATOM_OVERHEAD_BYTES for atom in receipt_atoms)
    number_of_atoms = len(receipt_atoms)
    storage_cost = calculate_storage_cost(block=block, total_bytes=total_bytes)
    record_value, record_atoms = build_storage_contract_record(
        owner_public_key=sender_public_key,
        creation_previous_block_hash=block.previous_block_hash,
        total_bytes=total_bytes,
        number_of_atoms=number_of_atoms,
    )

    if burn_account.data.get(node, receipt_id) is None:
        burn_account.data.put(node, receipt_id, record_value)
        burn_account.data_hash = burn_account.data.root_hash
        sender_account.balance -= storage_cost
        burn_account.balance += storage_cost
        if not hasattr(block, "contract_atoms") or block.contract_atoms is None:
            block.contract_atoms = []
        block.contract_atoms.extend(record_atoms)
        return storage_cost
    return 0
