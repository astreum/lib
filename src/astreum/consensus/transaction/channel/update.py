from __future__ import annotations

from typing import Any, Optional

from ....machine.models.expression import resolve_inner_exprs
from ....machine.models.expression import ZERO32
from ....utils.integer import bytes_to_int, int_to_bytes
from .model import Channel

RECIPIENT_SIZE = 32
WITHDRAWAL_WINDOW_SIZE = 8
PAYLOAD_RECIPIENT_ONLY_SIZE = RECIPIENT_SIZE
PAYLOAD_FULL_SIZE = RECIPIENT_SIZE + WITHDRAWAL_WINDOW_SIZE
CHANNEL_FIELD_COUNT = 3


def _parse_update_payload(payload: bytes) -> Optional[tuple[bytes, Optional[int]]]:
    payload_bytes = bytes(payload)
    if len(payload_bytes) == PAYLOAD_RECIPIENT_ONLY_SIZE:
        counterparty = payload_bytes[:RECIPIENT_SIZE]
        return counterparty, None

    if len(payload_bytes) != PAYLOAD_FULL_SIZE:
        return None

    counterparty = payload_bytes[:RECIPIENT_SIZE]
    withdrawal_window = bytes_to_int(payload_bytes[RECIPIENT_SIZE:PAYLOAD_FULL_SIZE])
    return counterparty, withdrawal_window


def get_channel_from_storage(node: Any, channel_head: Optional[bytes]) -> Optional[tuple[int, int, int]]:
    channel = Channel.from_storage(node, channel_head)
    if channel is None:
        return None
    return channel.balance, channel.counter, channel.withdrawal_window


def handle_channel_update(
    *,
    node: Any,
    block: Any,
    sender_account: Any,
    payload: bytes,
    tx_amount: int,
) -> bool:
    parsed_payload = _parse_update_payload(payload)
    if parsed_payload is None:
        return False
    counterparty, requested_withdrawal_window = parsed_payload

    if tx_amount < 0:
        return False

    current_channel_head = sender_account.channels.get(node, counterparty)
    decoded_record = get_channel_from_storage(node, current_channel_head)
    if decoded_record is None:
        return False
    current_balance, current_counter, current_withdrawal_window = decoded_record
    new_withdrawal_window = (
        current_withdrawal_window
        if requested_withdrawal_window is None
        else requested_withdrawal_window
    )

    # Do not allow shortening the withdrawal window.
    if new_withdrawal_window < current_withdrawal_window:
        return False

    updated_balance = current_balance
    if tx_amount > 0:
        updated_balance += int(tx_amount)
    updated_counter = current_counter + 1

    channel = Channel(
        balance=updated_balance,
        counter=updated_counter,
        withdrawal_window=new_withdrawal_window,
    )
    channel_expr = channel.expr()
    channel_head = channel_expr.hash()
    if not channel_head or channel_head == ZERO32:
        return False

    sender_account.channels.put(node, counterparty, channel_head)
    sender_account.channels_hash = sender_account.channels.root_hash or ZERO32
    inner_exprs, _ = resolve_inner_exprs(node, channel_expr)
    block.pending_exprs.extend(inner_exprs)
    return True
