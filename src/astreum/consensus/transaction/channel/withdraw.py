from __future__ import annotations

from typing import Any, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ....storage.models.atom import ZERO32, bytes_list_to_atoms
from .update import RECIPIENT_SIZE, get_channel_from_storage

OP_WITHDRAW = 2
COUNTER_SIZE = 8
AMOUNT_SIZE = 8
PAYLOAD_FIXED_SIZE = RECIPIENT_SIZE + COUNTER_SIZE + AMOUNT_SIZE
PAYLOAD_FIXED_WITH_OP_SIZE = 1 + PAYLOAD_FIXED_SIZE


def _parse_withdraw_payload(payload: bytes) -> Optional[tuple[bytes, int, int, bytes]]:
    payload_bytes = bytes(payload)
    if len(payload_bytes) >= PAYLOAD_FIXED_WITH_OP_SIZE and payload_bytes[0] == OP_WITHDRAW:
        payload_bytes = payload_bytes[1:]

    if len(payload_bytes) <= PAYLOAD_FIXED_SIZE:
        return None

    payer = payload_bytes[:RECIPIENT_SIZE]
    counter = int.from_bytes(
        payload_bytes[RECIPIENT_SIZE : RECIPIENT_SIZE + COUNTER_SIZE],
        "little",
        signed=False,
    )
    amount = int.from_bytes(
        payload_bytes[
            RECIPIENT_SIZE + COUNTER_SIZE : RECIPIENT_SIZE + COUNTER_SIZE + AMOUNT_SIZE
        ],
        "little",
        signed=False,
    )
    signature = payload_bytes[PAYLOAD_FIXED_SIZE:]
    return payer, counter, amount, signature


def _withdraw_message(
    *,
    chain_id: int,
    payer: bytes,
    recipient: bytes,
    counter: int,
    amount: int,
) -> bytes:
    return (
        OP_WITHDRAW.to_bytes(1, "little", signed=False)
        + chain_id.to_bytes(8, "little", signed=False)
        + bytes(payer)
        + bytes(recipient)
        + counter.to_bytes(COUNTER_SIZE, "little", signed=False)
        + amount.to_bytes(AMOUNT_SIZE, "little", signed=False)
    )


def handle_channel_withdraw(
    *,
    node: Any,
    block: Any,
    sender_account: Any,
    payload: bytes,
    chain_id: int,
    recipient: bytes,
) -> bool:
    parsed = _parse_withdraw_payload(payload)
    if parsed is None:
        return False
    payer, requested_counter, requested_amount, signature = parsed

    if requested_amount < 0:
        return False

    try:
        payer_public_key = Ed25519PublicKey.from_public_bytes(bytes(payer))
        payer_public_key.verify(
            signature,
            _withdraw_message(
                chain_id=chain_id,
                payer=payer,
                recipient=recipient,
                counter=requested_counter,
                amount=requested_amount,
            ),
        )
    except Exception:
        return False

    payer_account = block.accounts.get_account(address=payer, node=node)
    if payer_account is None:
        return False

    channel_head = payer_account.channels.get(node, recipient)
    channel_state = get_channel_from_storage(node, channel_head)
    if channel_state is None:
        return False
    channel_balance, stored_counter, withdrawal_window = channel_state

    if block.previous_block.timestamp is None:
        return False

    if block.previous_block.timestamp >= withdrawal_window:
        return False
    if requested_counter <= stored_counter:
        return False
    if requested_amount > channel_balance:
        return False

    updated_balance = channel_balance - requested_amount
    updated_channel_head, updated_channel_atoms = bytes_list_to_atoms(
        [
            updated_balance.to_bytes(max(1, (updated_balance.bit_length() + 7) // 8), "little", signed=False),
            requested_counter.to_bytes(COUNTER_SIZE, "little", signed=False),
            withdrawal_window.to_bytes(8, "little", signed=False),
        ]
    )
    if not updated_channel_head or updated_channel_head == ZERO32:
        return False

    payer_account.channels.put(node, recipient, updated_channel_head)
    payer_account.channels_hash = payer_account.channels.root_hash or ZERO32
    sender_account.balance += requested_amount

    if not hasattr(block, "contract_atoms") or block.contract_atoms is None:
        block.contract_atoms = []
    block.contract_atoms.extend(updated_channel_atoms)
    block.accounts.set_account(payer, payer_account)
    return True
