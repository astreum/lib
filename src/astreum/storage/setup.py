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
    for atom_path in level_0_path.glob("*.bin"):
        try:
            total += atom_path.stat().st_size
        except OSError:
            return 0
    return total


def storage_setup(node: Any, config: dict) -> None:
    """Initialize hot/cold storage helpers on the node."""

    node.logger.info("Setting up node storage")

    node.hot_storage = {}
    node.hot_storage_timestamps = {}
    node.storage_index = {}
    node.atom_advertisments = []
    node.atom_advertisments_lock = threading.RLock()
    node.storage_providers = []
    node.cold_storage_lock = threading.RLock()
    node.hot_storage_lock = threading.RLock()
    node.hot_storage_size = 0
    node.cold_storage_size = 0
    node.atom_fetch_interval = config["atom_fetch_interval"]
    node.atom_fetch_retries = config["atom_fetch_retries"]

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
        "Storage ready (hot_limit=%s bytes, cold_limit=%s bytes, cold_path=%s, atom_fetch_interval=%s, atom_fetch_retries=%s)",
        config["hot_storage_limit"],
        config["cold_storage_limit"],
        config["cold_storage_path"] or "disabled",
        config["atom_fetch_interval"],
        config["atom_fetch_retries"],
    )
