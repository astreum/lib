from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..models.atom import Atom


def _hot_storage_get(self, key: bytes) -> Optional[Atom]:
    """Retrieve an atom from in-memory cache while tracking hit statistics."""
    atom = self.hot_storage.get(key)
    if atom is not None:
        self.hot_storage_hits[key] = self.hot_storage_hits.get(key, 0) + 1
        self.logger.debug("Hot storage hit for %s", key.hex())
    else:
        self.logger.debug("Hot storage miss for %s", key.hex())
    return atom


def _network_get(self, key: bytes) -> Optional[Atom]:
    """Attempt to fetch an atom from network peers when local storage misses."""
    if not getattr(self, "is_connected", False):
        self.logger.debug("Network fetch skipped for %s; node not connected", key.hex())
        return None
    self.logger.debug("Attempting network fetch for %s", key.hex())
    try:
        from ...communication.handlers.object_request import (
            ObjectRequest,
            ObjectRequestType,
        )
        from ...communication.models.message import Message, MessageTopic
    except Exception as exc:
        self.logger.warning(
            "Communication module unavailable; cannot fetch %s: %s",
            key.hex(),
            exc,
        )
        return None

    try:
        closest_peer = self.peer_route.closest_peer_for_hash(key)
    except Exception as exc:
        self.logger.warning("Peer lookup failed for %s: %s", key.hex(), exc)
        return None

    if closest_peer is None or closest_peer.address is None:
        self.logger.debug("No peer available to fetch %s", key.hex())
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
        self.logger.warning("Failed to build object request for %s: %s", key.hex(), exc)
        return None

    # encrypt the outbound request for the target peer
    message.encrypt(closest_peer.shared_key_bytes)

    try:
        self.add_atom_req(key)
    except Exception as exc:
        self.logger.warning("Failed to track object request for %s: %s", key.hex(), exc)

    try:
        self.outgoing_queue.put((message.to_bytes(), closest_peer.address))
        self.logger.debug(
            "Queued OBJECT_GET for %s to peer %s",
            key.hex(),
            closest_peer.address,
        )
    except Exception as exc:
        self.logger.warning(
            "Failed to queue OBJECT_GET for %s to %s: %s",
            key.hex(),
            closest_peer.address,
            exc,
        )
    return None


def storage_get(self, key: bytes) -> Optional[Atom]:
    """Retrieve an Atom by checking local storage first, then the network."""
    self.logger.debug("Fetching atom %s", key.hex())
    atom = self._hot_storage_get(key)
    if atom is not None:
        self.logger.debug("Returning atom %s from hot storage", key.hex())
        return atom
    atom = self._cold_storage_get(key)
    if atom is not None:
        self.logger.debug("Returning atom %s from cold storage", key.hex())
        return atom
    
    if not self.is_connected:
        return None
    
    provider_payload = self.storage_index.get(key)
    if provider_payload is not None:
        try:
            from ...communication.handlers.object_response import decode_object_provider
            from ...communication.handlers.object_request import (
                ObjectRequest,
                ObjectRequestType,
            )
            from ...communication.models.message import Message, MessageTopic
            from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

            provider_key, provider_address, provider_port = decode_object_provider(provider_payload)
            provider_public_key = X25519PublicKey.from_public_bytes(provider_key)
            shared_key_bytes = self.relay_secret_key.exchange(provider_public_key)

            obj_req = ObjectRequest(
                type=ObjectRequestType.OBJECT_GET,
                data=b"",
                atom_id=key,
            )
            message = Message(
                topic=MessageTopic.OBJECT_REQUEST,
                content=obj_req.to_bytes(),
                sender=self.relay_public_key,
            )
            message.encrypt(shared_key_bytes)
            self.add_atom_req(key)
            self.outgoing_queue.put((message.to_bytes(), (provider_address, provider_port)))
            self.logger.debug(
                "Requested atom %s from indexed provider %s:%s",
                key.hex(),
                provider_address,
                provider_port,
            )
        except Exception as exc:
            self.logger.warning("Failed indexed fetch for %s: %s", key.hex(), exc)
        return None

    self.logger.debug("Falling back to network fetch for %s", key.hex())
    return self._network_get(key)


def local_get(self, key: bytes) -> Optional[Atom]:
    """Retrieve an Atom by checking only local hot and cold storage."""
    self.logger.debug("Fetching atom %s (local only)", key.hex())
    atom = self._hot_storage_get(key)
    if atom is not None:
        self.logger.debug("Returning atom %s from hot storage", key.hex())
        return atom
    atom = self._cold_storage_get(key)
    if atom is not None:
        self.logger.debug("Returning atom %s from cold storage", key.hex())
        return atom
    self.logger.debug("Local storage miss for %s", key.hex())
    return None


def _cold_storage_get(self, key: bytes) -> Optional[Atom]:
    """Read an atom from the cold storage directory if configured."""
    if not self.config["cold_storage_path"]:
        self.logger.debug("Cold storage disabled; cannot fetch %s", key.hex())
        return None
    filename = f"{key.hex().upper()}.bin"
    file_path = Path(self.config["cold_storage_path"]) / filename
    try:
        data = file_path.read_bytes()
    except FileNotFoundError:
        self.logger.debug("Cold storage miss for %s", key.hex())
        return None
    except OSError as exc:
        self.logger.warning("Error reading cold storage file %s: %s", file_path, exc)
        return None
    try:
        atom = Atom.from_bytes(data)
        self.logger.debug("Loaded atom %s from cold storage", key.hex())
        return atom
    except ValueError as exc:
        self.logger.warning("Cold storage data corrupted for %s: %s", file_path, exc)
        return None
