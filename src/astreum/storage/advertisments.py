import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .. import Node


def advertise_atoms(node: "Node", entries=None) -> None:
    """Advertise tracked atom ids to the closest known peer."""
    now = time.time()
    expired = 0
    to_advertise = []
    if entries is not None:
        for entry in entries:
            try:
                atom_id, payload_type, expires_at = entry
            except (TypeError, ValueError):
                node.logger.warning("Invalid atom advertisement entry: %r", entry)
                continue
            if expires_at is not None:
                try:
                    if expires_at <= now:
                        expired += 1
                        continue
                except TypeError:
                    node.logger.warning(
                        "Invalid atom advertisement expiry for %s: %r",
                        atom_id.hex(),
                        expires_at,
                    )
                    continue
            to_advertise.append(entry)
    else:
        with node.atom_advertisments_lock:
            if not node.atom_advertisments:
                node.logger.debug("No atom advertisements configured; skipping advertisement")
                return
            remaining = []
            for entry in node.atom_advertisments:
                try:
                    atom_id, payload_type, expires_at = entry
                except (TypeError, ValueError):
                    node.logger.warning("Invalid atom advertisement entry: %r", entry)
                    remaining.append(entry)
                    continue
                if expires_at is not None:
                    try:
                        if expires_at <= now:
                            expired += 1
                            continue
                    except TypeError:
                        node.logger.warning(
                            "Invalid atom advertisement expiry for %s: %r",
                            atom_id.hex(),
                            expires_at,
                        )
                        remaining.append(entry)
                        continue
                to_advertise.append(entry)
                remaining.append(entry)
            if len(remaining) != len(node.atom_advertisments):
                node.atom_advertisments = remaining

    advertised = 0
    for atom_id, payload_type, _expires_at in to_advertise:
        node._network_set(atom_id, payload_type=payload_type)
        advertised += 1

    node.logger.info(
        "Atom advertisement complete (advertised=%s, expired=%s)",
        advertised,
        expired,
    )
