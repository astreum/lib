from __future__ import annotations

import time
from queue import Empty
from typing import Any, Optional, Set, Tuple

from astreum.validation.models.fork import Fork
from astreum.validation.models.block import Block


def _process_peers_latest_block(
    node: Any, latest_block_hash: bytes, peer_ids: Set[Any]
) -> None:
    """Assign peers to the fork that matches their reported head."""
    node.logger.debug(
        "Processing %d peers reporting block %s",
        len(peer_ids),
        latest_block_hash.hex()
        if isinstance(latest_block_hash, (bytes, bytearray))
        else latest_block_hash,
    )
    new_fork = Fork(head=latest_block_hash)

    new_fork.verify(node)

    if new_fork.validated_upto and new_fork.validated_upto in node.forks:
        ref = node.forks[new_fork.validated_upto]
        if getattr(ref, "malicious_block_hash", None):
            node.logger.warning(
                "Skipping fork from block %s referencing malicious fork %s",
                latest_block_hash.hex()
                if isinstance(latest_block_hash, (bytes, bytearray))
                else latest_block_hash,
                new_fork.validated_upto.hex()
                if isinstance(new_fork.validated_upto, (bytes, bytearray))
                else new_fork.validated_upto,
            )
            return
        new_fork.root = ref.root
        new_fork.validated_upto = ref.validated_upto
        new_fork.chain_fork_position = ref.chain_fork_position

    for peer_id in peer_ids:
        new_fork.add_peer(peer_id)
        for head, fork in list(node.forks.items()):
            if head != latest_block_hash:
                fork.remove_peer(peer_id)

    node.forks[latest_block_hash] = new_fork
    node.logger.debug(
        "Fork %s now has %d peers (total forks %d)",
        latest_block_hash.hex()
        if isinstance(latest_block_hash, (bytes, bytearray))
        else latest_block_hash,
        len(new_fork.peers),
        len(node.forks),
    )


def _select_best_fork_head(node: Any) -> Optional[Tuple[bytes, Block, int]]:
    forks = getattr(node, "forks", None)
    if not isinstance(forks, dict) or not forks:
        return None

    config = getattr(node, "config", {}) or {}
    try:
        max_stale = int(config.get("verification_max_stale_seconds", 10))
    except (TypeError, ValueError):
        max_stale = 10
    try:
        max_future = int(config.get("verification_max_future_skew", 2))
    except (TypeError, ValueError):
        max_future = 2

    now = int(time.time())
    current_head = getattr(node, "latest_block_hash", None)

    best_head: Optional[bytes] = None
    best_block: Optional[Block] = None
    best_height: int = -1

    for head, fork in list(forks.items()):
        if getattr(fork, "malicious_block_hash", None):
            continue
        if not getattr(fork, "validated_upto", None):
            continue
        if not getattr(fork, "peers", None):
            continue
        if not isinstance(head, (bytes, bytearray)):
            continue

        try:
            block = Block.from_atom(node, head)
        except Exception:
            continue

        ts = getattr(block, "timestamp", None)
        if ts is None:
            continue
        ts_int = int(ts)
        if max_stale >= 0 and (now - ts_int) > max_stale:
            continue
        if max_future >= 0 and (ts_int - now) > max_future:
            continue

        height = int(getattr(block, "number", 0) or 0)
        if height > best_height:
            best_head = bytes(head)
            best_block = block
            best_height = height
            continue
        if height == best_height:
            if current_head == head:
                best_head = bytes(head)
                best_block = block
                best_height = height
            elif current_head != best_head and best_head is not None:
                if bytes(head) < bytes(best_head):
                    best_head = bytes(head)
                    best_block = block
                    best_height = height

    if best_head is None or best_block is None:
        return None
    return best_head, best_block, best_height


def make_verify_worker(node: Any):
    """Build the verify worker bound to the given node."""

    def _verify_worker() -> None:
        node.logger.info("Verify worker started")
        stop = node._verify_stop_event
        while not stop.is_set():
            batch: list[tuple[bytes, Set[Any]]] = []
            try:
                while True:
                    latest_b, peers = node._validation_verify_queue.get_nowait()
                    batch.append((latest_b, peers))
            except Empty:
                pass

            if not batch:
                node.logger.debug("Verify queue empty; sleeping")
                time.sleep(0.1)
                continue

            batch.sort(key=lambda item: len(item[1]), reverse=True)

            for latest_b, peers in batch:
                try:
                    _process_peers_latest_block(node, latest_b, peers)
                    node.logger.debug(
                        "Updated forks from block %s for %d peers",
                        latest_b.hex()
                        if isinstance(latest_b, (bytes, bytearray))
                        else latest_b,
                        len(peers),
                    )
                except Exception:
                    latest_hex = (
                        latest_b.hex()
                        if isinstance(latest_b, (bytes, bytearray))
                        else latest_b
                    )
                    node.logger.exception(
                        "Failed processing verification batch for %s", latest_hex
                    )

            selected = _select_best_fork_head(node)
            if selected is not None:
                selected_head, selected_block, selected_height = selected
                if getattr(node, "latest_block_hash", None) != selected_head:
                    node.latest_block_hash = selected_head
                    node.latest_block = selected_block
                    node.logger.info(
                        "Selected verified head %s (height=%s)",
                        selected_head.hex(),
                        selected_height,
                    )
        node.logger.info("Verify worker stopped")

    return _verify_worker
