from __future__ import annotations

import threading
import time
from queue import Queue, Empty
from typing import Any, Dict, Optional, Tuple

from .block import Block
from .chain import Chain
from .fork import Fork
from .._storage.atom import ZERO32, Atom


def validation_setup(node: Any) -> None:
    # Shared state
    node.validation_lock = getattr(node, "validation_lock", threading.RLock())

    # Public maps per your spec
    # - chains: Dict[root, Chain]
    # - forks:  Dict[head, Fork]
    node.chains = getattr(node, "chains", {})
    node.forks = getattr(node, "forks", {})

    # Single work queue of grouped items: (latest_block_hash, set(peer_ids))
    node._validation_verify_queue = getattr(
        node, "_validation_verify_queue", Queue()
    )
    node._validation_stop_event = getattr(
        node, "_validation_stop_event", threading.Event()
    )

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

    # Start workers as daemons
    node.validation_discovery_thread = threading.Thread(
        target=_discovery_worker, daemon=True, name="validation-discovery"
    )
    node.validation_verify_thread = threading.Thread(
        target=_verify_worker, daemon=True, name="validation-verify"
    )
    node.validation_discovery_thread.start()
    node.validation_verify_thread.start()
