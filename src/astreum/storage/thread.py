from __future__ import annotations

import time
from typing import TYPE_CHECKING

from .advertisments import advertise_atoms

if TYPE_CHECKING:
    from astreum.node import Node


_PRICE_MOVEMENT_TABLE: tuple[tuple[float, float], ...] = (
    (0.10, 0.60),  # -40%
    (0.20, 0.70),  # -30%
    (0.30, 0.80),  # -20%
    (0.40, 0.90),  # -10%
    (0.50, 0.96),  # -4%
    (0.60, 1.04),  # +4%
    (0.70, 1.12),  # +12%
    (0.80, 1.30),  # +30%
    (0.90, 1.70),  # +70%
    (1.00, 2.50),  # +150%
)


def _clamp01(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return value


def _incoming_queue_pressure(node: "Node") -> float:
    with node.incoming_queue_size_lock:
        size = int(node.incoming_queue_size or 0)
        limit = int(node.incoming_queue_size_limit or 0)

    if limit <= 0:
        return 0.0
    return _clamp01(size / limit)


def _price_movement_factor_for_pressure(pressure: float) -> float:
    p = _clamp01(float(pressure))
    for threshold, factor in _PRICE_MOVEMENT_TABLE:
        if p <= threshold:
            return factor
    return _PRICE_MOVEMENT_TABLE[-1][1]


def _update_storage_request_price(node: "Node") -> None:
    pressure = _incoming_queue_pressure(node)
    factor = _price_movement_factor_for_pressure(pressure)
    previous_price = node.storage_request_current_price
    target_price = max(node.config["storage_request_minimum_price"], int(round(previous_price * factor)))

    
    node.storage_request_current_price = target_price
    if previous_price != target_price:
        node.logger.debug(
            "Storage request price updated (price=%s prev=%s min=%s pressure=%.3f factor=%.3f)",
            target_price,
            previous_price,
            pressure,
            factor,
        )


def storage_thread(node: "Node") -> None:
    advertise_interval = float(node.config.get("storage_index_interval") or 0)
    price_interval = float(node.config.get("storage_request_price_interval") or 0)
    if advertise_interval <= 0 and price_interval <= 0:
        node.logger.info("Storage thread disabled (no advertise/price intervals configured)")
        return

    node.logger.info(
        "Storage thread started (advertise_interval=%ss, price_interval=%ss)",
        advertise_interval if advertise_interval > 0 else None,
        price_interval if price_interval > 0 else None,
    )
    stop = node.communication_stop_event
    now = time.monotonic()
    next_advertise_at = now if advertise_interval > 0 else None
    next_price_at = now if price_interval > 0 else None

    while not stop.is_set():
        now = time.monotonic()
        did_work = False

        if next_price_at is not None and now >= next_price_at:
            try:
                _update_storage_request_price(node)
            except Exception as exc:
                node.logger.exception("Storage request price update failed: %s", exc)
            did_work = True
            while next_price_at <= now:
                next_price_at += price_interval

        if next_advertise_at is not None and now >= next_advertise_at:
            try:
                # Keep storage index re-advertisements as a periodic task.
                advertised_ids, advertise_warning = advertise_atoms(node)
                if advertise_warning:
                    node.logger.warning(
                        "Storage advertisement batch had failures: advertised=%s reason=%s",
                        len(advertised_ids),
                        advertise_warning,
                    )
            except Exception as exc:
                node.logger.exception("Storage index re-advertisement failed: %s", exc)
            did_work = True
            while next_advertise_at <= now:
                next_advertise_at += advertise_interval

        if did_work:
            continue

        timeouts = []
        if next_price_at is not None:
            timeouts.append(max(0.0, next_price_at - now))
        if next_advertise_at is not None:
            timeouts.append(max(0.0, next_advertise_at - now))
        wait_timeout = min(timeouts) if timeouts else 1.0
        if stop.wait(wait_timeout):
            break

    node.logger.info("Storage thread stopped")
