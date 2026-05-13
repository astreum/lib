from __future__ import annotations

from typing import Any, Optional

from ....storage.models.atom import ZERO32, bytes_list_to_atoms
from ....utils.integer import int_to_bytes
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
    if int(withdrawal_window) >= int(previous_block_time):
        return False

    sender_account.balance += channel_balance

    # No trie delete yet: persist a zero-balance channel state to prevent re-refunds.
    updated_channel_head, updated_channel_atoms = bytes_list_to_atoms(
        [
            int_to_bytes(0),
            int_to_bytes(channel_counter + 1),
            int(withdrawal_window).to_bytes(8, "little", signed=False),
        ]
    )
    if not updated_channel_head or updated_channel_head == ZERO32:
        return False

    sender_account.channels.put(node, recipient, updated_channel_head)
    sender_account.channels_hash = sender_account.channels.root_hash or ZERO32
    block.pending_atoms.extend(updated_channel_atoms)
    return True
