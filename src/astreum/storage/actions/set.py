from __future__ import annotations

import socket
from time import time
from typing import Iterable, Tuple

from cryptography.hazmat.primitives import serialization

from ..models.atom import Atom
from ..providers import provider_id_for_payload


def _hot_storage_set(self, key: bytes, value: Atom) -> bool:
    """Store atom in hot storage without exceeding the configured limit."""
    node_logger = self.logger
    with self.hot_storage_lock:
        hot_limit = self.config["hot_storage_limit"]
        if value.size > hot_limit:
            node_logger.warning(
                "Hot storage limit too small for atom %s (bytes=%s, limit=%s)",
                key.hex(),
                value.size,
                hot_limit,
            )
            return False

        existing = self.hot_storage.get(key)
        existing_size = existing.size if existing is not None else 0
        projected = self.hot_storage_size - existing_size + value.size

        while projected > hot_limit:
            timestamps = self.hot_storage_timestamps
            if not timestamps:
                break
            if existing is not None and len(timestamps) == 1 and key in timestamps:
                break

            victim_key = None
            victim_ts = None
            for candidate_key, candidate_ts in timestamps.items():
                if existing is not None and candidate_key == key:
                    continue
                if victim_ts is None or candidate_ts < victim_ts:
                    victim_key = candidate_key
                    victim_ts = candidate_ts

            if victim_key is None:
                break

            victim = self.hot_storage.pop(victim_key, None)
            timestamps.pop(victim_key, None)
            if victim is not None:
                self.hot_storage_size -= victim.size

            projected = self.hot_storage_size - existing_size + value.size

        if projected > hot_limit:
            node_logger.warning(
                "Hot storage limit reached (%s > %s); skipping atom %s",
                projected,
                hot_limit,
                key.hex(),
            )
            return False

        if existing is not None:
            self.hot_storage_size -= existing_size

        self.hot_storage[key] = value
        self.hot_storage_timestamps[key] = time()
        self.hot_storage_size += value.size
        node_logger.debug(
            "Stored atom %s in hot storage (bytes=%s, total=%s)",
            key.hex(),
            value.size,
            self.hot_storage_size,
        )
        return True


def _network_set(self, atom_id: bytes, payload_type: int) -> None:
    """Advertise an atom id to the closest known peer so they can fetch it from us."""
    node_logger = self.logger
    atom_hex = atom_id.hex()
    try:
        from ...communication.handlers.object_request import (
            ObjectRequest,
            ObjectRequestType,
        )
        from ...communication.models.message import Message, MessageTopic
        from ...communication.outgoing_queue import enqueue_outgoing
    except Exception as exc:
        node_logger.warning(
            "Communication module unavailable; cannot advertise atom %s: %s",
            atom_hex,
            exc,
        )
        return
    try:
        # Advertise how other peers can reach this node for the requested atom.
        # The relay IP is the address we want others to dial for OBJECT_GETs.
        provider_ip = self.relay_ip_address
        # Keep the advertised port in sync with the node's incoming UDP port.
        provider_port = self.config["incoming_port"]

    except Exception as exc:
        node_logger.warning("Unable to determine provider address for atom %s: %s", atom_hex, exc,)
        return

    try:
        # Provider payload format: relay pubkey (32 bytes) + IPv4 (4 bytes) + port (2 bytes).
        # This is what peers decode to know where to send OBJECT_GET requests.
        provider_ip_bytes = socket.inet_aton(provider_ip)
        provider_port_bytes = int(provider_port).to_bytes(2, "big", signed=False)
        provider_key_bytes = self.config["relay_public_key_bytes"]
    except Exception as exc:
        node_logger.warning("Unable to encode provider info for %s: %s", atom_hex, exc)
        return

    provider_payload = provider_key_bytes + provider_ip_bytes + provider_port_bytes

    try:
        closest_peer = self.peer_route.closest_peer_for_hash(atom_id)
    except Exception as exc:
        node_logger.warning("Peer lookup failed for atom %s: %s", atom_hex, exc)
        return

    is_self_closest = False
    if closest_peer is None or closest_peer.address is None:
        is_self_closest = True
    else:
        try:
            from ...communication.util import xor_distance
        except Exception as exc:
            node_logger.warning("Failed to import xor_distance for atom %s: %s", atom_hex, exc)
            is_self_closest = True
        else:
            try:
                self_distance = xor_distance(atom_id, self.config["relay_public_key_bytes"])
                peer_distance = xor_distance(atom_id, closest_peer.public_key_bytes)
            except Exception as exc:
                node_logger.warning("Failed computing distance for atom %s: %s", atom_hex, exc)
                is_self_closest = True
            else:
                is_self_closest = self_distance <= peer_distance

    if is_self_closest:
        node_logger.debug("Self is closest; indexing provider for atom %s", atom_hex)
        provider_id = provider_id_for_payload(self, provider_payload)
        self.storage_index[atom_id] = provider_id
        return

    target_addr = closest_peer.address

    obj_req = ObjectRequest(
        type=ObjectRequestType.OBJECT_PUT,
        data=provider_payload,
        atom_id=atom_id,
        payload_type=payload_type,
    )
    
    message_body = obj_req.to_bytes()

    message = Message(
        topic=MessageTopic.OBJECT_REQUEST,
        content=message_body,
        sender=self.relay_public_key,
    )
    message.encrypt(closest_peer.shared_key_bytes)
    try:
        queued = enqueue_outgoing(
            self,
            target_addr,
            message=message,
            difficulty=closest_peer.difficulty,
        )
        if queued:
            node_logger.debug(
                "Advertised atom %s to peer at %s:%s",
                atom_hex,
                target_addr[0],
                target_addr[1],
            )
        else:
            node_logger.debug(
                "Dropped atom advertisement %s to peer at %s:%s",
                atom_hex,
                target_addr[0],
                target_addr[1],
            )
    except Exception as exc:
        node_logger.error(
            "Failed to queue advertisement for atom %s to %s:%s: %s",
            atom_hex,
            target_addr[0],
            target_addr[1],
            exc,
        )


def add_atom_advertisement(
    self,
    atom_id: bytes,
    payload_type: int,
    expires_at: float | None = None,
) -> None:
    """Track an atom id for periodic advertisement."""
    entry = (atom_id, payload_type, expires_at)
    lock = getattr(self, "atom_advertisments_lock", None)
    if lock is None:
        self.atom_advertisments.append(entry)
        return
    with lock:
        self.atom_advertisments.append(entry)


def add_atom_advertisements(
    self,
    entries: Iterable[Tuple[bytes, int, float | None]],
) -> None:
    """Track multiple atom ids for periodic advertisement."""
    lock = getattr(self, "atom_advertisments_lock", None)
    if lock is None:
        self.atom_advertisments.extend(entries)
        return
    with lock:
        self.atom_advertisments.extend(entries)
