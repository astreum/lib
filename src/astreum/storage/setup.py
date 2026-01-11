from __future__ import annotations

import threading
from typing import Any


def storage_setup(node: Any, config: dict) -> None:
    """Initialize hot/cold storage helpers on the node."""

    node.logger.info("Setting up node storage")

    node.hot_storage = {}
    node.hot_storage_hits = {}
    node.storage_index = {}
    node.atom_advertisments = []
    node.atom_advertisments_lock = threading.RLock()
    node.storage_providers = []
    node.hot_storage_size = 0
    node.cold_storage_size = 0
    node.atom_fetch_interval = config["atom_fetch_interval"]
    node.atom_fetch_retries = config["atom_fetch_retries"]

    node.logger.info(
        "Storage ready (hot_limit=%s bytes, cold_limit=%s bytes, cold_path=%s, atom_fetch_interval=%s, atom_fetch_retries=%s)",
        config["hot_storage_limit"],
        config["cold_storage_limit"],
        config["cold_storage_path"] or "disabled",
        config["atom_fetch_interval"],
        config["atom_fetch_retries"],
    )
