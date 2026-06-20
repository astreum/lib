from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

from .message_pow import NONCE_SIZE, calculate_message_nonce

if TYPE_CHECKING:
    from .models.message import Message
    from .. import Node


def enqueue_outgoing(
    node: "Node",
    address: Tuple[str, int],
    message: "Message",
    difficulty: int = 1,
) -> bool:
    """Enqueue an outgoing UDP payload."""
    # if not node.is_connected:
    #     raise RuntimeError("node is not connected; call node.connect() (communication_setup) first")

    if message.sender_public_key_bytes is None:
        message.sender_public_key_bytes = node.config["relay_public_key_bytes"]

    payload = message.to_bytes()

    try:
        difficulty_value = int(difficulty)
    except Exception:
        difficulty_value = 1
    if difficulty_value < 1:
        difficulty_value = 1

    try:
        nonce = calculate_message_nonce(payload, difficulty_value)
    except Exception as exc:
        node.logger.warning(
            "Failed generating message nonce (difficulty=%s bytes=%s): %s",
            difficulty_value,
            len(payload),
            exc,
        )
        return False

    payload = int(nonce).to_bytes(NONCE_SIZE, "big", signed=False) + payload

    node.outgoing_queue.put((payload, address))

    return True
