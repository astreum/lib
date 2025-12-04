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
    node_logger.debug("Attempting network fetch for %s", key.hex())
    # locate storage provider
    # query storage provider
    node_logger.warning("Network fetch for %s is not implemented", key.hex())
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


def _cold_storage_get(self, key: bytes) -> Optional[Atom]:
    """Read an atom from the cold storage directory if configured."""
    node_logger = self.logger
    if not self.cold_storage_path:
        node_logger.debug("Cold storage disabled; cannot fetch %s", key.hex())
        return None
    filename = f"{key.hex().upper()}.bin"
    file_path = Path(self.cold_storage_path) / filename
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
