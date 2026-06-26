from __future__ import annotations

from typing import Any

from blake3 import blake3

from ....machine.models.expression import Expr, resolve_inner_exprs
from ....machine.models.expression import ZERO32
from ....validation.models.block import Block
from ..model import Transaction
from .model import StorageRecord

LIST_ID_SIZE = 32
NONCE_SIZE = 64
DATA_HASH_SIZE = 32
PAYLOAD_SIZE = LIST_ID_SIZE + NONCE_SIZE + DATA_HASH_SIZE
PAYLOAD_WITH_FLAG_SIZE = 1 + PAYLOAD_SIZE


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

        record = StorageRecord.from_storage(node, contract_head.hash())
        if record is None:
            return False

        last_payment_block_hash = record.last_payment_block_hash
        if len(last_payment_block_hash) != LIST_ID_SIZE:
            return False

        atom_count = record.new_count
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
        challenged_link = None
        for hop in range(challenge_index + 1):
            link = node.get_expr(current_atom_id)
            if not isinstance(link, Expr.Link):
                return False
            challenged_link = link
            if hop < challenge_index:
                if not isinstance(link.tail, Expr.Link):
                    return False
                current_atom_id = link.tail.hash()
                if current_atom_id == ZERO32:
                    return False

        if challenged_link is None:
            return False

        head_expr = None
        if challenged_link.head is not None:
            head_expr = challenged_link.head
        elif challenged_link.head_hash is not None:
            head_expr = node.get_expr(challenged_link.head_hash)
        if head_expr is None or not isinstance(head_expr, Expr.Bytes):
            return False
        if blake3(head_expr.value).digest() != challenge_data_hash:
            return False

        total_bytes = record.new_size
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

        updated_record = StorageRecord(
            creation_block_hash=record.creation_block_hash,
            last_payment_block_hash=block.previous_block_hash,
            last_payment_winner=bytes(transaction.sender),
            new_size=record.new_size,
            new_count=record.new_count,
        )
        updated_record_head = updated_record.expr().hash()

        burn_account.data.put(node, atom_list_id, updated_record_head)
        burn_account.data_hash = burn_account.data.root_hash

        inner_exprs, _ = resolve_inner_exprs(node, updated_record.expr())
        block.pending_exprs.extend(inner_exprs)
        return True
    except Exception:
        return False
