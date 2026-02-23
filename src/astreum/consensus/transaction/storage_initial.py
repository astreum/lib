from __future__ import annotations

from typing import Any

from ..block.iaar import calculate_storage_fee
from ...storage.models.atom import Atom, ZERO32, bytes_list_to_atoms
from ...utils.integer import int_to_bytes
from .model import Transaction

ATOM_OVERHEAD_BYTES = 33  # next_id (32) + kind (1)


def build_storage_contract_record(
    *,
    owner_public_key: bytes,
    creation_previous_block_hash: bytes,
    total_bytes: int,
    number_of_atoms: int,
) -> tuple[bytes, list[Atom]]:
    record_fields = [
        # owner_public_key
        owner_public_key,
        # creation_block_hash
        creation_previous_block_hash,
        # last_payment_block_hash
        creation_previous_block_hash,
        # last_payment_winner
        ZERO32,
        # total_bytes
        int_to_bytes(total_bytes),
        # number_of_atoms
        int_to_bytes(number_of_atoms),
    ]
    return bytes_list_to_atoms(record_fields)


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

        list_atoms = node.get_atom_list(atom_list_id)
        if list_atoms is None:
            return None

        total_bytes = sum(len(atom.data) + ATOM_OVERHEAD_BYTES for atom in list_atoms)
        number_of_atoms = len(list_atoms)

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

        if not hasattr(block, "contract_atoms") or block.contract_atoms is None:
            block.contract_atoms = []
        block.contract_atoms.extend(record_atoms)
        return storage_cost
    except Exception:
        return None
