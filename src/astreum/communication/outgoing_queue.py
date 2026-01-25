from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

from .message_pow import NONCE_SIZE, calculate_message_nonce

if TYPE_CHECKING:
    from .models.message import Message
    from .. import Node


OUTGOING_QUEUE_ITEM_OVERHEAD_BYTES = 6
def enqueue_outgoing(
    node: "Node",
    address: Tuple[str, int],
    message: "Message",
    difficulty: int = 1,
) -> bool:
    """Enqueue an outgoing UDP payload while tracking queued bytes.
    When used, it increments `node.outgoing_queue_size` by `len(payload) + 6` and enforces
    `node.outgoing_queue_size_limit` (bytes) as a soft cap by dropping enqueues that
    would exceed the limit. If `node.outgoing_queue_timeout` is > 0, it waits up to
    that many seconds (using `communication_stop_event.wait`) for space before dropping.
    """
    # if not node.is_connected:
    #     raise RuntimeError("node is not connected; call node.connect() (communication_setup) first")

    # Autofill sender public key if missing
    if message.sender_public_key_bytes is None:
        message.sender_public_key_bytes = node.config["relay_public_key_bytes"]

    # Auto-fill sender incoming port if missing
    if message.incoming_port is None:
        message.incoming_port = node.config["incoming_port"]

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

    accounted_size = len(payload) + OUTGOING_QUEUE_ITEM_OVERHEAD_BYTES

    timeout = float(node.outgoing_queue_timeout or 0)

    with node.outgoing_queue_size_lock:
        current_size = int(node.outgoing_queue_size)
        limit = int(node.outgoing_queue_size_limit)
        projected_size = current_size + accounted_size
        if projected_size > limit:
            if timeout <= 0:
                node.logger.warning(
                    "Outgoing queue size limit reached (%s > %s); dropping outbound payload (bytes=%s)",
                    projected_size,
                    limit,
                    len(payload),
                )
                return False
            wait_for_space = True
        else:
            node.outgoing_queue_size = projected_size
            wait_for_space = False

    if wait_for_space:
        if node.communication_stop_event.wait(timeout):
            return False
        if not node.is_connected:
            return False
        with node.outgoing_queue_size_lock:
            current_size = int(node.outgoing_queue_size)
            limit = int(node.outgoing_queue_size_limit)
            projected_size = current_size + accounted_size
            if limit and projected_size > limit:
                node.logger.warning(
                    "Outgoing queue still full after waiting %ss (%s > %s); dropping outbound payload (bytes=%s)",
                    timeout,
                    projected_size,
                    limit,
                    len(payload),
                )
                return False
            node.outgoing_queue_size = projected_size

    try:
        node.outgoing_queue.put((payload, address, accounted_size))
    except Exception:
        with node.outgoing_queue_size_lock:
            node.outgoing_queue_size = max(0, int(node.outgoing_queue_size) - accounted_size)
        raise

    return True
