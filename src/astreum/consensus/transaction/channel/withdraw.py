from __future__ import annotations

from typing import Any, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ....machine.models.expression import resolve_inner_exprs
from ....machine.models.expression import ZERO32
from ....storage.radix import get_from_radix_tree, put_in_radix_tree
from .model import Channel
from .update import get_channel_from_storage

OP_WITHDRAW = 2
COUNTER_SIZE = 8
AMOUNT_SIZE = 8
SIGNATURE_SIZE = 64
PAYLOAD_FIXED_SIZE = COUNTER_SIZE + AMOUNT_SIZE
PAYLOAD_WITH_SIGNATURE_SIZE = PAYLOAD_FIXED_SIZE + SIGNATURE_SIZE
PAYLOAD_WITH_SIGNATURE_WITH_OP_SIZE = 1 + PAYLOAD_WITH_SIGNATURE_SIZE


def _parse_withdraw_payload(payload: bytes) -> Optional[tuple[int, int, bytes]]:
    payload_bytes = payload
    if len(payload_bytes) == PAYLOAD_WITH_SIGNATURE_WITH_OP_SIZE:
        if payload_bytes[0] != OP_WITHDRAW:
            return None
        payload_bytes = payload_bytes[1:]
    elif len(payload_bytes) != PAYLOAD_WITH_SIGNATURE_SIZE:
        return None

    counter = int.from_bytes(
        payload_bytes[:COUNTER_SIZE],
        "little",
        signed=False,
    )
    amount = int.from_bytes(
        payload_bytes[COUNTER_SIZE : COUNTER_SIZE + AMOUNT_SIZE],
        "little",
        signed=False,
    )
    signature = payload_bytes[PAYLOAD_FIXED_SIZE:]
    return counter, amount, signature


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
        + payer
        + recipient
        + counter.to_bytes(COUNTER_SIZE, "little", signed=False)
        + amount.to_bytes(AMOUNT_SIZE, "little", signed=False)
    )


def handle_channel_withdraw(
    *,
    node: Any,
    block: Any,
    sender_account: Any,
    transaction: Any,
) -> bool:
    payload = transaction.data.value if transaction.data._tag == "bytes" else b""
    chain_id = transaction.chain_id
    recipient = transaction.sender
    expected_payer = transaction.recipient

    parsed = _parse_withdraw_payload(payload)
    if parsed is None:
        return False
    requested_counter, requested_amount, signature = parsed
    payer = expected_payer

    if requested_amount < 0:
        return False

    try:
        payer_public_key = Ed25519PublicKey.from_public_bytes(payer)
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

    channel_head = get_from_radix_tree(payer_account.channels, node, recipient)
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
    channel = Channel(
        balance=updated_balance,
        counter=requested_counter,
        withdrawal_window=withdrawal_window,
    )
    channel_expr = channel.expr()
    updated_channel_head = channel_expr.hash()
    if not updated_channel_head or updated_channel_head == ZERO32:
        return False

    put_in_radix_tree(payer_account.channels, node, recipient, updated_channel_head)
    payer_account.channels_hash = payer_account.channels.root_hash or ZERO32
    sender_account.balance += requested_amount

    inner_exprs, _ = resolve_inner_exprs(node, channel_expr)
    block.pending_exprs.extend(inner_exprs)
    block.accounts.set_account(payer, payer_account)
    return True
