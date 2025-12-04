from __future__ import annotations

import threading
from queue import Queue
from typing import Any, Optional

from .validator import current_validator  # re-exported for compatibility
from .workers import (
    make_discovery_worker,
    make_validation_worker,
    make_verify_worker,
)
from ..utils.bytes import hex_to_bytes


def consensus_setup(node: Any, config: Optional[dict] = None) -> None:
    config = config or {}
    node.logger.info("Setting up node consensus")

    # Shared state
    node.validation_lock = getattr(node, "validation_lock", threading.RLock())

    # Public maps per your spec
    # - chains: Dict[root, Chain]
    # - forks:  Dict[head, Fork]
    node.chains = getattr(node, "chains", {})
    node.forks = getattr(node, "forks", {})
    node.logger.info(
        "Consensus maps initialized (chains=%s, forks=%s)",
        len(node.chains),
        len(node.forks),
    )

    latest_block_hex = config.get("latest_block_hash")
    if latest_block_hex is not None:
        node.latest_block_hash = hex_to_bytes(latest_block_hex, expected_length=32)
    
    node.latest_block_hash = getattr(node, "latest_block_hash", None)
    node.latest_block = getattr(node, "latest_block", None)
    node.logger.info(
        "Consensus latest_block_hash preset: %s",
        node.latest_block_hash.hex() if isinstance(node.latest_block_hash, bytes) else node.latest_block_hash,
    )

    # Pending transactions queue (hash-only entries)
    node._validation_transaction_queue = getattr(
        node, "_validation_transaction_queue", Queue()
    )
    # Single work queue of grouped items: (latest_block_hash, set(peer_ids))
    node._validation_verify_queue = getattr(
        node, "_validation_verify_queue", Queue()
    )
    node._validation_stop_event = getattr(
        node, "_validation_stop_event", threading.Event()
    )

    def enqueue_transaction_hash(tx_hash: bytes) -> None:
        """Schedule a transaction hash for validation processing."""
        if not isinstance(tx_hash, (bytes, bytearray)):
            raise TypeError("transaction hash must be bytes-like")
        node._validation_transaction_queue.put(bytes(tx_hash))

    node.enqueue_transaction_hash = enqueue_transaction_hash

    verify_worker = make_verify_worker(node)
    validation_worker = make_validation_worker(node)

    # Start workers as daemons
    discovery_worker = make_discovery_worker(node)
    node.consensus_discovery_thread = threading.Thread(
        target=discovery_worker, daemon=True, name="consensus-discovery"
    )
    node.consensus_verify_thread = threading.Thread(
        target=verify_worker, daemon=True, name="consensus-verify"
    )
    node.consensus_validation_thread = threading.Thread(
        target=validation_worker, daemon=True, name="consensus-validation"
    )
    node.consensus_discovery_thread.start()
    node.logger.info("Started consensus discovery thread (%s)", node.consensus_discovery_thread.name)
    node.consensus_verify_thread.start()
    node.logger.info("Started consensus verify thread (%s)", node.consensus_verify_thread.name)
    node.logger.info("Consensus setup ready")
