from __future__ import annotations

import time
from queue import Empty
from typing import Any, Dict, Set, Tuple


def make_discovery_worker(node: Any):
    """
    Build the discovery worker bound to the given node.

    The returned callable mirrors the previous inline worker in ``setup.py``.
    """

    def _discovery_worker() -> None:
        stop = node._validation_stop_event
        while not stop.is_set():
            try:
                peers = getattr(node, "peers", None)
                if isinstance(peers, dict):
                    pairs: list[Tuple[Any, bytes]] = [
                        (peer_id, bytes(latest))
                        for peer_id, peer in list(peers.items())
                        if isinstance(
                            (latest := getattr(peer, "latest_block", None)),
                            (bytes, bytearray),
                        )
                        and latest
                    ]
                    latest_keys: Set[bytes] = {hb for _, hb in pairs}
                    grouped: Dict[bytes, set[Any]] = {
                        hb: {pid for pid, phb in pairs if phb == hb}
                        for hb in latest_keys
                    }

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

    return _discovery_worker
