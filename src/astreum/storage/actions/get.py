from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..models.atom import Atom


def _hot_storage_get(self, key: bytes) -> Optional[Atom]:
    """Retrieve an atom from in-memory cache while tracking hit statistics."""
    node_logger = self.logger
    atom = self.hot_storage.get(key)
    if atom is not None:
        self.hot_storage_hits[key] = self.hot_storage_hits.get(key, 0) + 1
        node_logger.debug("Hot storage hit for %s", key.hex())
    else:
        node_logger.debug("Hot storage miss for %s", key.hex())
    return atom


def _network_get(self, key: bytes) -> Optional[Atom]:
    """Attempt to fetch an atom from network peers when local storage misses."""
    node_logger = self.logger
    if not getattr(self, "is_connected", False):
        node_logger.debug("Network fetch skipped for %s; node not connected", key.hex())
        return None
    node_logger.debug("Attempting network fetch for %s", key.hex())
    try:
        from ...communication.handlers.object_request import (
            ObjectRequest,
            ObjectRequestType,
        )
        from ...communication.models.message import Message, MessageTopic
    except Exception as exc:
        node_logger.warning(
            "Communication module unavailable; cannot fetch %s: %s",
            key.hex(),
            exc,
        )
        return None

    try:
        closest_peer = self.peer_route.closest_peer_for_hash(key)
    except Exception as exc:
        node_logger.warning("Peer lookup failed for %s: %s", key.hex(), exc)
        return None

    if closest_peer is None or closest_peer.address is None:
        node_logger.debug("No peer available to fetch %s", key.hex())
        return None

    obj_req = ObjectRequest(
        type=ObjectRequestType.OBJECT_GET,
        data=b"",
        atom_id=key,
    )
    try:
        message = Message(
            topic=MessageTopic.OBJECT_REQUEST,
            content=obj_req.to_bytes(),
            sender=self.relay_public_key,
        )
    except Exception as exc:
        node_logger.warning("Failed to build object request for %s: %s", key.hex(), exc)
        return None

    try:
        self.add_atom_req(key)
    except Exception as exc:
        node_logger.warning("Failed to track object request for %s: %s", key.hex(), exc)

    try:
        self.outgoing_queue.put((message.to_bytes(), closest_peer.address))
        node_logger.debug(
            "Queued OBJECT_GET for %s to peer %s",
            key.hex(),
            closest_peer.address,
        )
    except Exception as exc:
        node_logger.warning(
            "Failed to queue OBJECT_GET for %s to %s: %s",
            key.hex(),
            closest_peer.address,
            exc,
        )
    return None


def storage_get(self, key: bytes) -> Optional[Atom]:
    """Retrieve an Atom by checking local storage first, then the network."""
    node_logger = self.logger
    node_logger.debug("Fetching atom %s", key.hex())
    atom = self._hot_storage_get(key)
    if atom is not None:
        node_logger.debug("Returning atom %s from hot storage", key.hex())
        return atom
    atom = self._cold_storage_get(key)
    if atom is not None:
        node_logger.debug("Returning atom %s from cold storage", key.hex())
        return atom
    node_logger.debug("Falling back to network fetch for %s", key.hex())
    return self._network_get(key)


def local_get(self, key: bytes) -> Optional[Atom]:
    """Retrieve an Atom by checking only local hot and cold storage."""
    node_logger = self.logger
    node_logger.debug("Fetching atom %s (local only)", key.hex())
    atom = self._hot_storage_get(key)
    if atom is not None:
        node_logger.debug("Returning atom %s from hot storage", key.hex())
        return atom
    atom = self._cold_storage_get(key)
    if atom is not None:
        node_logger.debug("Returning atom %s from cold storage", key.hex())
        return atom
    node_logger.debug("Local storage miss for %s", key.hex())
    return None


def _cold_storage_get(self, key: bytes) -> Optional[Atom]:
    """Read an atom from the cold storage directory if configured."""
    node_logger = self.logger
    if not self.config["cold_storage_path"]:
        node_logger.debug("Cold storage disabled; cannot fetch %s", key.hex())
        return None
    filename = f"{key.hex().upper()}.bin"
    file_path = Path(self.config["cold_storage_path"]) / filename
    try:
        data = file_path.read_bytes()
    except FileNotFoundError:
        node_logger.debug("Cold storage miss for %s", key.hex())
        return None
    except OSError as exc:
        node_logger.warning("Error reading cold storage file %s: %s", file_path, exc)
        return None
    try:
        atom = Atom.from_bytes(data)
        node_logger.debug("Loaded atom %s from cold storage", key.hex())
        return atom
    except ValueError as exc:
        node_logger.warning("Cold storage data corrupted for %s: %s", file_path, exc)
        return None
