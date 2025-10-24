from __future__ import annotations

import threading
from queue import Queue
from typing import Any, Optional

from .workers import (
    make_discovery_worker,
    make_validation_worker,
    make_verify_worker,
)
from .genesis import create_genesis_block
from ..utils.bytes import hex_to_bytes


def current_validator(node: Any) -> bytes:
    """Return the current validator identifier. Override downstream."""
    raise NotImplementedError("current_validator must be implemented by the host node")


def consensus_setup(node: Any, config: Optional[dict] = None) -> None:
    config = config or {}

    # Shared state
    node.validation_lock = getattr(node, "validation_lock", threading.RLock())

    # Public maps per your spec
    # - chains: Dict[root, Chain]
    # - forks:  Dict[head, Fork]
    node.chains = getattr(node, "chains", {})
    node.forks = getattr(node, "forks", {})

    node.latest_block_hash = None
    latest_block_hex = config.get("latest_block_hash")
    if latest_block_hex is not None:
        node.latest_block_hash = hex_to_bytes(latest_block_hex, expected_length=32)
    node.latest_block = None

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
    validation_worker = make_validation_worker(
        node, current_validator=current_validator
    )

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
    node.consensus_verify_thread.start()

    validator_secret_hex = config.get("validation_secret_key")
    if validator_secret_hex:
        validator_secret_bytes = hex_to_bytes(validator_secret_hex, expected_length=32)
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import ed25519

            validator_private = ed25519.Ed25519PrivateKey.from_private_bytes(
                validator_secret_bytes
            )
        except Exception as exc:
            raise ValueError("invalid validation_secret_key") from exc

        validator_public_bytes = validator_private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        node.validation_secret_key = validator_private
        node.validation_public_key = validator_public_bytes

        if node.latest_block_hash is None:
            genesis_block = create_genesis_block(
                node,
                validator_public_key=validator_public_bytes,
                validator_secret_key=validator_secret_bytes,
            )
            genesis_hash, genesis_atoms = genesis_block.to_atom()
            if hasattr(node, "_local_set"):
                for atom in genesis_atoms:
                    try:
                        node._local_set(atom.object_id(), atom)
                    except Exception:
                        pass
            node.latest_block_hash = genesis_hash
            node.latest_block = genesis_block

        node.consensus_validation_thread.start()
