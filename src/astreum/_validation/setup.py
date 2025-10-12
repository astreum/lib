from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Any, Dict, Optional, Tuple

from cryptography.hazmat.primitives import serialization

from .block import Block
from .chain import Chain
from .fork import Fork
from .._storage.atom import ZERO32, Atom


@dataclass
class Transaction:
    """Lightweight transaction view for validation processing."""

    recipient: bytes
    sender: bytes
    amount: int
    counter: int


def current_validator(node: Any) -> bytes:
    """Return the current validator identifier. Override downstream."""
    raise NotImplementedError("current_validator must be implemented by the host node")


def apply_transaction(node: Any, block: object, transaction_hash: bytes) -> None:
    """Apply transaction to the candidate block. Override downstream."""
    pass


def validation_setup(node: Any) -> None:
    # Shared state
    node.validation_lock = getattr(node, "validation_lock", threading.RLock())

    # Public maps per your spec
    # - chains: Dict[root, Chain]
    # - forks:  Dict[head, Fork]
    node.chains = getattr(node, "chains", {})
    node.forks = getattr(node, "forks", {})

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

    def _process_peers_latest_block(latest_block_hash: bytes, peer_ids: set[Any]) -> None:
        """Assign a peer to a fork for its latest block without merging forks.

        Flow:
        - Create a new Fork for `latest_block_hash` and validate it, using
          stop_heads composed of current fork heads to short-circuit when
          ancestry meets an existing fork head.
        - If a matching fork head is found and is not malicious, copy its
          structural fields (root, validated_upto, chain_fork_position) onto
          the new fork.
        - Add all peers in `peer_ids` to the new fork and remove each from any
          previous fork they followed.
        - Persist the new fork under `node.forks[latest_block_hash]`.
        """
        new_fork = Fork(head=latest_block_hash)

        current_fork_heads = {fk.head for fk in node.forks.values() if fk.head != latest_block_hash}

        new_fork.validate(storage_get=node._local_get, stop_heads=current_fork_heads)

        # update new_fork with details of the fork with head of validated_upto
        if new_fork.validated_upto and new_fork.validated_upto in node.forks:
            ref = node.forks[new_fork.validated_upto]
            # if the matched fork is malicious, disregard this new fork entirely
            if getattr(ref, "malicious_block_hash", None):
                return
            # copy structural fields exactly
            new_fork.root = ref.root
            new_fork.validated_upto = ref.validated_upto
            new_fork.chain_fork_position = ref.chain_fork_position

        # add peers to new fork and remove them from any old forks
        for peer_id in peer_ids:
            new_fork.add_peer(peer_id)
            # Remove this peer from all other forks
            for h, fk in list(node.forks.items()):
                if h != latest_block_hash:
                    fk.remove_peer(peer_id)

        # persist the fork
        node.forks[latest_block_hash] = new_fork


    # Discovery worker: watches peers and enqueues head changes
    def _discovery_worker():
        stop = node._validation_stop_event
        while not stop.is_set():
            try:
                peers = getattr(node, "peers", None)
                if isinstance(peers, dict):
                    # Snapshot as (peer_id, latest_block_hash) pairs
                    pairs = [
                        (peer_id, bytes(latest))
                        for peer_id, peer in list(peers.items())
                        if isinstance((latest := getattr(peer, "latest_block", None)), (bytes, bytearray)) and latest
                    ]
                    # Group peers by latest block hash
                    latest_keys = {hb for _, hb in pairs}
                    grouped: Dict[bytes, set[Any]] = {
                        hb: {pid for pid, phb in pairs if phb == hb}
                        for hb in latest_keys
                    }

                    # Replace queue contents with current groups
                    try:
                        while True:
                            node._validation_verify_queue.get_nowait()
                    except Empty:
                        pass
                    for latest_b, peer_set in grouped.items():
                        node._validation_verify_queue.put((latest_b, peer_set))
            except Exception:
                pass
            finally:
                time.sleep(0.5)

    # Verification worker: computes root/height and applies peer→fork assignment
    def _verify_worker():
        stop = node._validation_stop_event
        while not stop.is_set():
            # Take a snapshot of all currently queued groups
            batch: list[tuple[bytes, set[Any]]] = []
            try:
                while True:
                    item = node._validation_verify_queue.get_nowait()
                    batch.append(item)
            except Empty:
                pass

            if not batch:
                time.sleep(0.1)
                continue

            # Process the snapshot; new items enqueued during processing
            # will be handled in the next iteration
            for latest_b, peers in batch:
                try:
                    _process_peers_latest_block(latest_b, peers)
                except Exception:
                    pass

    def _validation_worker() -> None:
        """Consume pending transactions when scheduled to validate."""
        stop = node._validation_stop_event
        while not stop.is_set():
            validation_public_key = getattr(node, "validation_public_key", None)
            if not validation_public_key:
                time.sleep(0.5)
                continue

            scheduled_validator = current_validator(node)

            if scheduled_validator != validation_public_key:
                time.sleep(0.5)
                continue

            try:
                current_hash = node._validation_transaction_queue.get_nowait()
            except Empty:
                time.sleep(0.1)
                continue

            new_block = Block()
            new_block.validator_public_key = getattr(node, "validation_public_key", None)
            
            while True:
                try:
                    apply_transaction(node, new_block, current_hash)
                except NotImplementedError:
                    node._validation_transaction_queue.put(current_hash)
                    time.sleep(0.5)
                    break
                except Exception:
                    # Skip problematic transaction; leave block as-is.
                    pass

                try:
                    current_hash = node._validation_transaction_queue.get_nowait()
                except Empty:
                    break

    # Start workers as daemons
    node.validation_discovery_thread = threading.Thread(
        target=_discovery_worker, daemon=True, name="validation-discovery"
    )
    node.validation_verify_thread = threading.Thread(
        target=_verify_worker, daemon=True, name="validation-verify"
    )
    node.validation_worker_thread = threading.Thread(
        target=_validation_worker, daemon=True, name="validation-worker"
    )
    node.validation_discovery_thread.start()
    node.validation_verify_thread.start()
    if getattr(node, "validation_secret_key", None):
        node.validation_worker_thread.start()
