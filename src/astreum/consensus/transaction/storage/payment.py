from __future__ import annotations

from typing import Any

from blake3 import blake3

from ....storage.models.atom import ZERO32, bytes_list_to_atoms
from ....utils.integer import bytes_to_int
from ....validation.models.block import Block
from ..model import Transaction

LIST_ID_SIZE = 32
NONCE_SIZE = 64
DATA_HASH_SIZE = 32
PAYLOAD_SIZE = LIST_ID_SIZE + NONCE_SIZE + DATA_HASH_SIZE
PAYLOAD_WITH_FLAG_SIZE = 1 + PAYLOAD_SIZE
STORAGE_RECORD_FIELD_COUNT = 6
LAST_PAYMENT_BLOCK_HASH_INDEX = 2
LAST_PAYMENT_WINNER_INDEX = 3
TOTAL_BYTES_INDEX = 4
ATOM_COUNT_INDEX = 5


def _leading_zero_bits(buf: bytes) -> int:
    zeros = 0
    for byte in buf:
        if byte == 0:
            zeros += 8
            continue
        zeros += 8 - int(byte).bit_length()
        break
    return zeros


def _required_bits(*, provider_key: bytes, atom_list_id: bytes) -> int:
    if len(provider_key) != LIST_ID_SIZE or len(atom_list_id) != LIST_ID_SIZE:
        return 0
    distance = int.from_bytes(
        bytes(a ^ b for a, b in zip(provider_key, atom_list_id)),
        "big",
        signed=False,
    )
    if distance == 0:
        return 0
    return distance.bit_length() - 1


def _parse_payload(payload: bytes) -> tuple[bytes, bytes, bytes] | None:
    payload_bytes = bytes(payload)
    if len(payload_bytes) == PAYLOAD_WITH_FLAG_SIZE:
        # Accept payloads that include an inner storage-payment flag.
        if payload_bytes[0] != 1:
            return None
        payload_bytes = payload_bytes[1:]
    elif len(payload_bytes) != PAYLOAD_SIZE:
        return None

    atom_list_id = payload_bytes[:LIST_ID_SIZE]
    nonce = payload_bytes[LIST_ID_SIZE : LIST_ID_SIZE + NONCE_SIZE]
    challenge_data_hash = payload_bytes[LIST_ID_SIZE + NONCE_SIZE : PAYLOAD_SIZE]
    return atom_list_id, nonce, challenge_data_hash


def handle_storage_payment_contract(
    *,
    node: Any,
    block: object,
    transaction: Transaction,
    sender_account: Any,
    burn_account: Any,
    payload: bytes,
) -> bool:
    """Handle a storage-payment contract transaction sent to burn address."""
    try:
        parsed_payload = _parse_payload(payload)
        if parsed_payload is None:
            return False
        atom_list_id, nonce, challenge_data_hash = parsed_payload

        contract_head = burn_account.data.get(node, atom_list_id)
        if not contract_head or contract_head == ZERO32:
            return False

        contract_atoms = node.get_atom_list(bytes(contract_head))
        if contract_atoms is None or len(contract_atoms) < STORAGE_RECORD_FIELD_COUNT:
            return False

        contract_fields = [
            bytes(atom.data) for atom in contract_atoms[:STORAGE_RECORD_FIELD_COUNT]
        ]
        last_payment_block_hash = contract_fields[LAST_PAYMENT_BLOCK_HASH_INDEX]
        if len(last_payment_block_hash) != LIST_ID_SIZE:
            return False

        atom_count = bytes_to_int(contract_fields[ATOM_COUNT_INDEX])
        if atom_count <= 0:
            return False

        required_bits = _required_bits(
            provider_key=bytes(transaction.sender),
            atom_list_id=atom_list_id,
        )
        work_hash = blake3(
            last_payment_block_hash
            + bytes(transaction.sender)
            + atom_list_id
            + challenge_data_hash
            + nonce
        ).digest()
        if _leading_zero_bits(work_hash) < required_bits:
            return False

        challenge_seed = blake3(last_payment_block_hash + atom_list_id).digest()
        challenge_index = (
            int.from_bytes(challenge_seed[:8], "little", signed=False) % atom_count
        )

        current_atom_id = atom_list_id
        challenged_atom = None
        for hop in range(challenge_index + 1):
            atom = node.get_atom(current_atom_id)
            if atom is None:
                return False
            if atom.object_id() != current_atom_id:
                return False
            challenged_atom = atom
            if hop < challenge_index:
                if atom.next_id == ZERO32:
                    return False
                current_atom_id = atom.next_id

        if challenged_atom is None:
            return False
        if blake3(challenged_atom.data).digest() != challenge_data_hash:
            return False

        total_bytes = bytes_to_int(contract_fields[TOTAL_BYTES_INDEX])
        if total_bytes <= 0:
            return False
        
        last_payment_block = Block.from_storage(node, last_payment_block_hash)
        
        if block.height <= last_payment_block.height:
            return False
        payout = total_bytes * (block.height - last_payment_block.height)
        if payout <= 0:
            return False

        sender_account.balance += payout
        block.total_mint += payout

        contract_fields[LAST_PAYMENT_BLOCK_HASH_INDEX] = block.previous_block_hash
        contract_fields[LAST_PAYMENT_WINNER_INDEX] = bytes(transaction.sender)
        updated_contract_head, updated_contract_atoms = bytes_list_to_atoms(contract_fields)

        burn_account.data.put(node, atom_list_id, updated_contract_head)
        burn_account.data_hash = burn_account.data.root_hash

        block.pending_atoms.extend(updated_contract_atoms)
        return True
    except Exception:
        return False
