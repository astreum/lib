import time
from typing import TYPE_CHECKING

from .put.network import put_expr_in_network

if TYPE_CHECKING:
    from .. import Node


def advertise_exprs(
    node: "Node", entries=None
) -> tuple[list[bytes], str | None]:
    """Advertise tracked expr ids to the closest known peer."""
    now = time.time()
    expired = 0
    to_advertise = []
    failed = 0
    first_reason = None
    if entries is not None:
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
    else:
        with node.expr_advertisements_lock:
            if not node.expr_advertisements:
                node.logger.debug("No expr advertisements configured; skipping advertisement")
                return [], None
            remaining = []
            for entry in node.expr_advertisements:
                try:
                    expr_id, payload_type, expires_at = entry
                except (TypeError, ValueError):
                    node.logger.debug("Invalid expr advertisement entry: %r", entry)
                    failed += 1
                    if first_reason is None:
                        first_reason = "invalid expr advertisement entry"
                    remaining.append(entry)
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
                        remaining.append(entry)
                        continue
                to_advertise.append(entry)
                remaining.append(entry)
            if len(remaining) != len(node.expr_advertisements):
                node.expr_advertisements = remaining

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
