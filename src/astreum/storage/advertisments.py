import time
from typing import TYPE_CHECKING

from astreum.storage.put.network import put_expr_in_network

if TYPE_CHECKING:
    from astreum import Node


def advertise_exprs(
    node: "Node", entries
) -> tuple[list[bytes], str | None]:
    """Advertise the given expr entries to the closest known peer."""
    now = time.time()
    expired = 0
    to_advertise = []
    failed = 0
    first_reason = None
    for entry in entries:
        try:
            expr_id, payload_type, expires_at = entry
        except (TypeError, ValueError):
            node.logger.debug("Invalid expr advertisement entry: %r", entry)
            failed += 1
            if first_reason is None:
                first_reason = "invalid expr advertisement entry"
            continue
        if expires_at is not None:
            try:
                if expires_at <= now:
                    expired += 1
                    continue
            except TypeError:
                node.logger.debug(
                    "Invalid expr advertisement expiry for %s: %r",
                    expr_id.hex(),
                    expires_at,
                )
                failed += 1
                if first_reason is None:
                    first_reason = f"invalid expr advertisement expiry for {expr_id.hex()}"
                continue
        to_advertise.append(entry)

    advertised_ids: list[bytes] = []
    for expr_id, payload_type, _expires_at in to_advertise:
        queued, reason = put_expr_in_network(node, expr_id, payload_type=payload_type)
        if queued:
            advertised_ids.append(expr_id)
        else:
            failed += 1
            if first_reason is None:
                first_reason = reason

    warning_reason = None
    if failed:
        warning_reason = (
            f"{failed} advertisement(s) failed; first reason: {first_reason or 'unknown'}"
        )

    node.logger.info(
        "Expr advertisement complete (advertised=%s, expired=%s, failed=%s)",
        len(advertised_ids),
        expired,
        failed,
    )
    return advertised_ids, warning_reason
