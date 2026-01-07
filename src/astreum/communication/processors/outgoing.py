from __future__ import annotations

from queue import Empty
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from .. import Node

def process_outgoing_messages(node: "Node") -> None:
    """Send queued outbound packets."""
    stop = getattr(node, "communication_stop_event", None)
    while stop is None or not stop.is_set():
        try:
            item = node.outgoing_queue.get(timeout=0.5)
        except Empty:
            continue
        except Exception:
            node.logger.exception("Error taking from outgoing queue")
            continue

        payload = None
        addr = None
        accounted_size = None
        if isinstance(item, tuple) and len(item) == 3:
            payload, addr, accounted_size = item
        elif isinstance(item, tuple) and len(item) == 2:
            payload, addr = item
        else:
            node.logger.warning("Outgoing queue item has unexpected shape: %r", item)
            continue

        if stop is not None and stop.is_set():
            if accounted_size is not None:
                try:
                    with node.outgoing_queue_size_lock:
                        node.outgoing_queue_size = max(0, node.outgoing_queue_size - int(accounted_size))
                except Exception:
                    node.logger.exception("Failed updating outgoing_queue_size on shutdown")
            break

        try:
            node.outgoing_socket.sendto(payload, addr)
        except Exception as exc:
            node.logger.warning("Error sending message to %s: %s", addr, exc)
        finally:
            if accounted_size is not None:
                try:
                    with node.outgoing_queue_size_lock:
                        node.outgoing_queue_size = max(0, node.outgoing_queue_size - int(accounted_size))
                except Exception:
                    node.logger.exception("Failed updating outgoing_queue_size")

    node.logger.info("Outgoing message processor stopped")
