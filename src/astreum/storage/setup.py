from __future__ import annotations

import threading
from pathlib import Path
from typing import Any


def _cold_level_0_size(cold_path: str | None) -> int:
    if not cold_path:
        return 0
    level_0_path = Path(cold_path) / "level_0"
    if not level_0_path.exists() or not level_0_path.is_dir():
        return 0
    total = 0
    for expr_path in level_0_path.glob("*.bin"):
        try:
            total += expr_path.stat().st_size
        except OSError:
            return 0
    return total


def setup_storage(node: Any, config: dict) -> None:
    """Initialize hot and cold storage infrastructure on a Node.

    Creates the in-memory hot storage cache, initializes the cold
    storage directory structure on disk (``level_0``), and measures
    the existing cold storage size for capacity tracking.

    Args:
        node: A Node instance to attach storage attributes to.
        config: The node configuration dict, expected to contain
            ``hot_storage_limit``, ``cold_storage_path``,
            ``cold_storage_limit``, ``storage_fetch_interval``,
            and ``storage_fetch_retries``.
    """

    node.logger.info("Setting up node storage")

    node.hot_storage = {}
    node.hot_storage_timestamps = {}
    node.storage_index = {}
    node.storage_slot_registry = {}
    node.storage_records_held = set()
    node.expr_advertisements = []
    node.expr_advertisements_lock = threading.RLock()
    node.storage_providers = []
    node.claim_spacing_eras = {}
    node.cold_storage_lock = threading.RLock()
    node.hot_storage_lock = threading.RLock()
    node.hot_storage_size = 0
    node.cold_storage_size = 0
    node.storage_fetch_interval = config["storage_fetch_interval"]
    node.storage_fetch_retries = config["storage_fetch_retries"]

    cold_path = config.get("cold_storage_path")
    if cold_path:
        try:
            cold_root = Path(cold_path)
            cold_root.mkdir(parents=True, exist_ok=True)
            (cold_root / "level_0").mkdir(parents=True, exist_ok=True)
        except OSError:
            node.logger.warning("Disabling cold storage; unable to create level_0 in %s", cold_path)
            config["cold_storage_path"] = None

    node.cold_storage_level_0_size = _cold_level_0_size(config.get("cold_storage_path"))

    node.logger.info(
        "Storage ready (hot_limit=%s bytes, cold_limit=%s bytes, cold_path=%s, storage_fetch_interval=%s, storage_fetch_retries=%s)",
        config["hot_storage_limit"],
        config["cold_storage_limit"],
        config["cold_storage_path"] or "disabled",
        config["storage_fetch_interval"],
        config["storage_fetch_retries"],
    )
