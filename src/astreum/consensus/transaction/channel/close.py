from __future__ import annotations

from typing import Any, Optional

from ....machine.models.expression import resolve_inner_exprs
from ....machine.models.expression import ZERO32
from .model import Channel
from .update import RECIPIENT_SIZE, get_channel_from_storage

OP_CLOSE = 3
PAYLOAD_RECIPIENT_ONLY_SIZE = RECIPIENT_SIZE
PAYLOAD_RECIPIENT_ONLY_WITH_OP_SIZE = 1 + PAYLOAD_RECIPIENT_ONLY_SIZE


def _parse_close_payload(payload: bytes) -> Optional[bytes]:
    payload_bytes = bytes(payload)
    if len(payload_bytes) == PAYLOAD_RECIPIENT_ONLY_WITH_OP_SIZE:
        if payload_bytes[0] != OP_CLOSE:
            return None
        payload_bytes = payload_bytes[1:]
    elif len(payload_bytes) != PAYLOAD_RECIPIENT_ONLY_SIZE:
        return None

    return payload_bytes[:RECIPIENT_SIZE]


def handle_channel_close(
    *,
    node: Any,
    block: Any,
    sender_account: Any,
    payload: bytes,
) -> bool:
    recipient = _parse_close_payload(payload)
    if recipient is None:
        return False

    previous_block = getattr(block, "previous_block", None)
    previous_block_time = getattr(previous_block, "timestamp", None)
    if previous_block_time is None:
        return False

    channel_head = sender_account.channels.get(node, recipient)
    channel_state = get_channel_from_storage(node, channel_head)
    if channel_state is None:
        return False
    channel_balance, channel_counter, withdrawal_window = channel_state

    # Close is valid only after the withdrawal window has passed.
    if withdrawal_window >= int(previous_block_time):
        return False

    sender_account.balance += channel_balance

    channel = Channel(
        balance=0,
        counter=channel_counter + 1,
        withdrawal_window=withdrawal_window,
    )
    channel_expr = channel.expr()
    updated_channel_head = channel_expr.hash()
    if not updated_channel_head or updated_channel_head == ZERO32:
        return False

    sender_account.channels.put(node, recipient, updated_channel_head)
    sender_account.channels_hash = sender_account.channels.root_hash or ZERO32
    inner_exprs, _ = resolve_inner_exprs(node, channel_expr)
    block.pending_exprs.extend(inner_exprs)
    return True
