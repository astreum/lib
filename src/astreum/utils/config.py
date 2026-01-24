
from pathlib import Path
from typing import Dict

DEFAULT_HOT_STORAGE_LIMIT = 1 << 30  # 1 GiB
DEFAULT_COLD_STORAGE_LIMIT = 10 << 30  # 10 GiB
DEFAULT_COLD_STORAGE_SCALE = "MB"
DEFAULT_INCOMING_PORT = 52780
DEFAULT_LOGGING_RETENTION_DAYS = 7
DEFAULT_PEER_TIMEOUT_SECONDS = 15 * 60  # 15 minutes
DEFAULT_PEER_TIMEOUT_INTERVAL_SECONDS = 10  # 10 seconds
DEFAULT_BOOTSTRAP_RETRY_INTERVAL_SECONDS = 30  # 30 seconds
DEFAULT_STORAGE_INDEX_INTERVAL_SECONDS = 600  # 10 minutes
DEFAULT_ATOM_FETCH_INTERVAL_SECONDS = 0.25
DEFAULT_ATOM_FETCH_RETRIES = 8
DEFAULT_INCOMING_QUEUE_SIZE_LIMIT_BYTES = 64 * 1024 * 1024  # 64 MiB
DEFAULT_INCOMING_QUEUE_TIMEOUT_SECONDS = 1.0
DEFAULT_OUTGOING_QUEUE_SIZE_LIMIT_BYTES = 64 * 1024 * 1024  # 64 MiB
DEFAULT_OUTGOING_QUEUE_TIMEOUT_SECONDS = 1.0
DEFAULT_SEED = "bootstrap.astreum.org:52780"
DEFAULT_VERIFICATION_MAX_STALE_SECONDS = 10
DEFAULT_VERIFICATION_MAX_FUTURE_SKEW_SECONDS = 2


def config_setup(config: Dict = {}):
    """
    Normalize configuration values before the node starts.
    """
    chain_str = config.get("chain")
    if chain_str not in {"main", "test"}:
        chain_str = None
    chain_id_raw = config.get("chain_id")
    if chain_id_raw is None:
        chain_id = 1 if chain_str == "main" else 0
    else:
        try:
            chain_id = int(chain_id_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"chain_id must be an integer: {chain_id_raw!r}"
            ) from exc
    if chain_str is None:
        chain_str = "main" if chain_id == 1 else "test"
    config["chain"] = chain_str
    config["chain_id"] = chain_id

    hot_limit_raw = config.get(
        "hot_storage_limit", config.get("hot_storage_default_limit", DEFAULT_HOT_STORAGE_LIMIT)
    )
    try:
        config["hot_storage_limit"] = int(hot_limit_raw)
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

    cold_scale_raw = config.get("cold_storage_scale", DEFAULT_COLD_STORAGE_SCALE)
    if isinstance(cold_scale_raw, str):
        cold_scale = cold_scale_raw.strip().upper()
    else:
        raise ValueError("cold_storage_scale must be a string")
    scale_bytes = {"KB": 1_000, "MB": 1_000_000, "GB": 1_000_000_000}
    if cold_scale not in scale_bytes:
        raise ValueError("cold_storage_scale must be one of: KB, MB, GB")
    config["cold_storage_scale"] = cold_scale
    config["cold_storage_base_size"] = scale_bytes[cold_scale]

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

    retention_raw = config.get(
        "logging_retention_days",
        config.get("logging_retention", config.get("retention_days", DEFAULT_LOGGING_RETENTION_DAYS)),
    )
    try:
        config["logging_retention_days"] = int(retention_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"logging_retention_days must be an integer: {retention_raw!r}"
        ) from exc

    if "incoming_port" in config:
        incoming_port_raw = config["incoming_port"]
    else:
        incoming_port_raw = DEFAULT_INCOMING_PORT
    try:
        config["incoming_port"] = int(incoming_port_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"incoming_port must be an integer: {incoming_port_raw!r}"
        ) from exc
    if config["incoming_port"] < 0:
        raise ValueError("incoming_port must be 0 or a positive integer")

    incoming_queue_limit_raw = config.get(
        "incoming_queue_size_limit", DEFAULT_INCOMING_QUEUE_SIZE_LIMIT_BYTES
    )
    try:
        incoming_queue_limit = int(incoming_queue_limit_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"incoming_queue_size_limit must be an integer: {incoming_queue_limit_raw!r}"
        ) from exc
    if incoming_queue_limit < 0:
        raise ValueError("incoming_queue_size_limit must be a non-negative integer")
    config["incoming_queue_size_limit"] = incoming_queue_limit

    incoming_queue_timeout_raw = config.get(
        "incoming_queue_timeout", DEFAULT_INCOMING_QUEUE_TIMEOUT_SECONDS
    )
    try:
        incoming_queue_timeout = float(incoming_queue_timeout_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"incoming_queue_timeout must be a number: {incoming_queue_timeout_raw!r}"
        ) from exc
    if incoming_queue_timeout < 0:
        raise ValueError("incoming_queue_timeout must be a non-negative number")
    config["incoming_queue_timeout"] = incoming_queue_timeout

    peer_timeout_raw = config.get("peer_timeout", DEFAULT_PEER_TIMEOUT_SECONDS)
    try:
        peer_timeout = int(peer_timeout_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"peer_timeout must be an integer: {peer_timeout_raw!r}"
        ) from exc

    if peer_timeout <= 0:
        raise ValueError("peer_timeout must be a positive integer")

    config["peer_timeout"] = peer_timeout

    interval_raw = config.get("peer_timeout_interval", DEFAULT_PEER_TIMEOUT_INTERVAL_SECONDS)
    try:
        interval = int(interval_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"peer_timeout_interval must be an integer: {interval_raw!r}"
        ) from exc

    if interval <= 0:
        raise ValueError("peer_timeout_interval must be a positive integer")

    config["peer_timeout_interval"] = interval
    verify_interval_raw = config.get("verify_blockchain_interval", interval)
    try:
        verify_interval = float(verify_interval_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"verify_blockchain_interval must be a number: {verify_interval_raw!r}"
        ) from exc
    if verify_interval <= 0:
        raise ValueError("verify_blockchain_interval must be a positive number")
    config["verify_blockchain_interval"] = verify_interval

    bootstrap_retry_raw = config.get(
        "bootstrap_retry_interval", DEFAULT_BOOTSTRAP_RETRY_INTERVAL_SECONDS
    )
    try:
        bootstrap_retry_interval = int(bootstrap_retry_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"bootstrap_retry_interval must be an integer: {bootstrap_retry_raw!r}"
        ) from exc
    if bootstrap_retry_interval <= 0:
        raise ValueError("bootstrap_retry_interval must be a positive integer")
    config["bootstrap_retry_interval"] = bootstrap_retry_interval

    storage_index_raw = config.get(
        "storage_index_interval", DEFAULT_STORAGE_INDEX_INTERVAL_SECONDS
    )
    try:
        storage_index_interval = int(storage_index_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"storage_index_interval must be an integer: {storage_index_raw!r}"
        ) from exc
    if storage_index_interval <= 0:
        raise ValueError("storage_index_interval must be a positive integer")
    config["storage_index_interval"] = storage_index_interval

    atom_fetch_interval_raw = config.get(
        "atom_fetch_interval", DEFAULT_ATOM_FETCH_INTERVAL_SECONDS
    )
    try:
        atom_fetch_interval = float(atom_fetch_interval_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"atom_fetch_interval must be a number: {atom_fetch_interval_raw!r}"
        ) from exc
    if atom_fetch_interval < 0:
        raise ValueError("atom_fetch_interval must be a non-negative number")
    config["atom_fetch_interval"] = atom_fetch_interval

    atom_fetch_retries_raw = config.get(
        "atom_fetch_retries", DEFAULT_ATOM_FETCH_RETRIES
    )
    try:
        atom_fetch_retries = int(atom_fetch_retries_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"atom_fetch_retries must be an integer: {atom_fetch_retries_raw!r}"
        ) from exc
    if atom_fetch_retries < 0:
        raise ValueError("atom_fetch_retries must be a non-negative integer")
    config["atom_fetch_retries"] = atom_fetch_retries

    outgoing_queue_limit_raw = config.get(
        "outgoing_queue_size_limit", DEFAULT_OUTGOING_QUEUE_SIZE_LIMIT_BYTES
    )
    try:
        outgoing_queue_limit = int(outgoing_queue_limit_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"outgoing_queue_size_limit must be an integer: {outgoing_queue_limit_raw!r}"
        ) from exc
    if outgoing_queue_limit < 0:
        raise ValueError("outgoing_queue_size_limit must be a non-negative integer")
    config["outgoing_queue_size_limit"] = outgoing_queue_limit

    outgoing_queue_timeout_raw = config.get(
        "outgoing_queue_timeout", DEFAULT_OUTGOING_QUEUE_TIMEOUT_SECONDS
    )
    try:
        outgoing_queue_timeout = float(outgoing_queue_timeout_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"outgoing_queue_timeout must be a number: {outgoing_queue_timeout_raw!r}"
        ) from exc
    if outgoing_queue_timeout < 0:
        raise ValueError("outgoing_queue_timeout must be a non-negative number")
    config["outgoing_queue_timeout"] = outgoing_queue_timeout

    max_stale_raw = config.get(
        "verification_max_stale_seconds", DEFAULT_VERIFICATION_MAX_STALE_SECONDS
    )
    try:
        max_stale = int(max_stale_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"verification_max_stale_seconds must be an integer: {max_stale_raw!r}"
        ) from exc
    if max_stale < 0:
        raise ValueError("verification_max_stale_seconds must be a non-negative integer")
    config["verification_max_stale_seconds"] = max_stale

    max_future_raw = config.get(
        "verification_max_future_skew", DEFAULT_VERIFICATION_MAX_FUTURE_SKEW_SECONDS
    )
    try:
        max_future = int(max_future_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"verification_max_future_skew must be an integer: {max_future_raw!r}"
        ) from exc
    if max_future < 0:
        raise ValueError("verification_max_future_skew must be a non-negative integer")
    config["verification_max_future_skew"] = max_future

    if "default_seeds" in config:
        raise ValueError("default_seeds is no longer supported; use default_seed")

    if "default_seed" in config:
        default_seed_raw = config["default_seed"]
    else:
        default_seed_raw = DEFAULT_SEED

    if default_seed_raw is None:
        config["default_seed"] = None
    elif isinstance(default_seed_raw, str):
        config["default_seed"] = default_seed_raw
    else:
        raise ValueError("default_seed must be a string or None")

    if "default_seed" not in config:
        config["default_seed"] = None

    additional_seeds_raw = config.get("additional_seeds", [])
    if isinstance(additional_seeds_raw, (list, tuple)):
        config["additional_seeds"] = list(additional_seeds_raw)
    else:
        raise ValueError("additional_seeds must be a list of strings")

    verified_up_to_raw = config.get("verified_up_to")
    if verified_up_to_raw in (None, ""):
        config["verified_up_to"] = None
    elif isinstance(verified_up_to_raw, str):
        config["verified_up_to"] = verified_up_to_raw
    else:
        raise ValueError("verified_up_to must be a hex string or None")

    if "validator_secret_key" not in config:
        config["validator_secret_key"] = None

    return config
