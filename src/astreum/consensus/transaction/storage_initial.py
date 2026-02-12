from __future__ import annotations

from typing import Any

from ...storage.models.atom import Atom, ZERO32, bytes_list_to_atoms
from ...utils.integer import int_to_bytes
from .model import Transaction


def handle_storage_initial_contract(
    *,
    node: Any,
    block: object,
    transaction: Transaction,
    sender_account: Any,
    burn_account: Any,
    payload: bytes,
    tx_fee: int,
) -> list[Atom]:
    """Handle a storage-initial contract transaction sent to burn address."""
    try:
        list_head_id = payload
        if len(list_head_id) != 32:
            return []

        existing_record = None
        burn_data_root = getattr(burn_account.data, "root_hash", None)
        if burn_data_root not in (None, b"", ZERO32):
            existing_record = burn_account.data.get(node, list_head_id)
        if existing_record is not None:
            return []

        list_atoms = node.get_atom_list(list_head_id)
        if list_atoms is None:
            return []

        total_bytes = sum(len(atom.data) for atom in list_atoms)
        number_of_atoms = len(list_atoms)

        numerator = total_bytes * block.previous_block.cumulative_stake
        storage_cost = (numerator + block.previous_block.cumulative_total_fees - 1) // block.previous_block.cumulative_total_fees
        required_balance = tx_fee + storage_cost
        if sender_account.balance < required_balance:
            return []

        record_fields = [
            # owner_public_key
            transaction.sender,
            # creation_block_hash
            block.previous_block_hash,
            # last_payment_block_hash
            block.previous_block_hash,
            # last_payment_winner
            ZERO32,
            # total_bytes
            int_to_bytes(total_bytes),
            # number_of_atoms
            int_to_bytes(number_of_atoms),
        ]
        record_value, record_atoms = bytes_list_to_atoms(record_fields)

        burn_account.data.put(node, list_head_id, record_value)
        burn_account.data_hash = burn_account.data.root_hash
        burn_account.balance += storage_cost
        sender_account.balance -= storage_cost

        return record_atoms
    except Exception:
        return []
