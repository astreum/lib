
from pathlib import Path
from typing import Dict

DEFAULT_HOT_STORAGE_LIMIT = 1 << 30  # 1 GiB
DEFAULT_COLD_STORAGE_LIMIT = 10 << 30  # 10 GiB


def config_setup(config: Dict = {}):
    """
    Normalize configuration values before the node starts.
    """
    chain_str = config.get("chain", "test")
    if chain_str not in {"main", "test"}:
        chain_str = "test"
    config["chain"] = chain_str
    config["chain_id"] = 1 if chain_str == "main" else 0

    hot_limit_raw = config.get(
        "hot_storage_limit", config.get("hot_storage_default_limit", DEFAULT_HOT_STORAGE_LIMIT)
    )
    try:
        config["hot_storage_default_limit"] = int(hot_limit_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"hot_storage_limit must be an integer: {hot_limit_raw!r}"
        ) from exc

    cold_limit_raw = config.get("cold_storage_limit", DEFAULT_COLD_STORAGE_LIMIT)
    try:
        config["cold_storage_limit"] = int(cold_limit_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"cold_storage_limit must be an integer: {cold_limit_raw!r}"
        ) from exc

    cold_path_raw = config.get("cold_storage_path")
    if cold_path_raw:
        try:
            path_obj = Path(cold_path_raw)
            path_obj.mkdir(parents=True, exist_ok=True)
            config["cold_storage_path"] = str(path_obj)
        except OSError:
            config["cold_storage_path"] = None
    else:
        config["cold_storage_path"] = None

    return config
