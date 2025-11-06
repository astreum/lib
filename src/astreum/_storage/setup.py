from __future__ import annotations

from pathlib import Path
from typing import Any


def storage_setup(node: Any, config: dict) -> None:
    """Initialize hot/cold storage helpers on the node."""

    node.hot_storage = {}
    node.hot_storage_hits = {}
    node.storage_index = {}
    node.hot_storage_size = 0
    hot_storage_default_limit = 1 << 30  # 1 GiB
    hot_storage_limit_value = config.get("hot_storage_limit", hot_storage_default_limit)
    try:
        node.hot_storage_limit = int(hot_storage_limit_value)
    except (TypeError, ValueError):
        node.hot_storage_limit = hot_storage_default_limit

    node.cold_storage_size = 0
    cold_storage_default_limit = 10 << 30  # 10 GiB
    cold_storage_limit_value = config.get("cold_storage_limit", cold_storage_default_limit)
    try:
        node.cold_storage_limit = int(cold_storage_limit_value)
    except (TypeError, ValueError):
        node.cold_storage_limit = cold_storage_default_limit

    cold_storage_path = config.get("cold_storage_path")
    if cold_storage_path:
        try:
            Path(cold_storage_path).mkdir(parents=True, exist_ok=True)
        except OSError:
            cold_storage_path = None
    node.cold_storage_path = cold_storage_path
