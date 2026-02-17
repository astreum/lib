from __future__ import annotations

from typing import TYPE_CHECKING

from .advertisments import advertise_atoms

if TYPE_CHECKING:
    from astreum.node import Node


def storage_thread(node: "Node") -> None:
    interval = node.config.get("storage_index_interval")
    if not interval:
        node.logger.info("Storage thread disabled")
        return

    node.logger.info("Storage thread started (interval=%ss)", interval)
    stop = node.communication_stop_event

    while not stop.is_set():
        try:
            # Keep storage index re-advertisements as the first loop action.
            advertise_atoms(node)
        except Exception as exc:
            node.logger.exception("Storage index re-advertisement failed: %s", exc)

        if stop.wait(interval):
            break

    node.logger.info("Storage thread stopped")
