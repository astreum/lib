from __future__ import annotations

from typing import Any

from ...storage.models.atom import Atom, ZERO32, bytes_list_to_atoms
from ...utils.integer import int_to_bytes
from .model import Transaction

ATOM_OVERHEAD_BYTES = 33  # next_id (32) + kind (1)


def calculate_storage_cost(*, block: object, total_bytes: int) -> int:
    numerator = total_bytes * block.previous_block.cumulative_stake
    return (numerator + block.previous_block.cumulative_total_fees - 1) // block.previous_block.cumulative_total_fees


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
) -> bool:
    """Handle a storage-initial contract transaction sent to burn address."""
    try:
        existing_record = burn_account.data.get(node, atom_list_id)
        if existing_record is not None:
            return False

        list_atoms = node.get_atom_list(atom_list_id)
        if list_atoms is None:
            return False

        total_bytes = sum(len(atom.data) + ATOM_OVERHEAD_BYTES for atom in list_atoms)
        number_of_atoms = len(list_atoms)

        storage_cost = calculate_storage_cost(block=block, total_bytes=total_bytes)
        if sender_account.balance < current_fees + storage_cost:
            return False

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
        return True
    except Exception:
        return False
