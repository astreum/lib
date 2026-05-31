from __future__ import annotations

import socket
from time import time
from typing import Iterable, Tuple

from cryptography.hazmat.primitives import serialization

from ..providers import provider_id_for_payload


def _hot_storage_set(node, expr: "Expr") -> bool:
    """Store an Expr in hot storage keyed by its hash."""
    from ...machine.models.expression import Expr

    key = expr.hash()
    node_logger = node.logger
    with node.hot_storage_lock:
        hot_limit = node.config["hot_storage_limit"]
        size = expr.size()
        if size > hot_limit:
            return False

        existing = node.hot_storage.get(key)
        existing_size = existing.size() if existing is not None else 0
        projected = node.hot_storage_size - existing_size + size

        while projected > hot_limit:
            timestamps = node.hot_storage_timestamps
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

            victim = node.hot_storage.pop(victim_key, None)
            timestamps.pop(victim_key, None)
            if victim is not None:
                node.hot_storage_size -= victim.size()

            projected = node.hot_storage_size - existing_size + size

        if projected > hot_limit:
            return False

        if existing is not None:
            node.hot_storage_size -= existing_size

        node.hot_storage[key] = expr
        node.hot_storage_timestamps[key] = time()
        node.hot_storage_size += size
        return True


def _network_set(self, expr_id: bytes, payload_type: int) -> tuple[bool, str | None]:
    """Advertise an expr id to the closest known peer so they can fetch it from us."""
    node_logger = self.logger
    expr_hex = expr_id.hex()
    try:
        from ...communication.object_request.code import ObjectRequestCode
        from ...communication.object_request.model import ObjectRequest
        from ...communication.models.message import Message, MessageTopic
        from ...communication.outgoing_queue import enqueue_outgoing
    except Exception as exc:
        node_logger.debug(
            "Communication module unavailable; cannot advertise expr %s: %s",
            expr_hex,
            exc,
        )
        return False, f"communication module unavailable: {exc}"
    try:
        # Advertise how other peers can reach this node for the requested expr.
        # The relay IP is the address we want others to dial for OBJECT_GETs.
        provider_ip = self.relay_ip_address
        # Keep the advertised port in sync with the node's incoming UDP port.
        provider_port = self.config["incoming_port"]

    except Exception as exc:
        node_logger.debug("Unable to determine provider address for expr %s: %s", expr_hex, exc,)
        return False, f"unable to determine provider address: {exc}"

    try:
        # Provider payload format: relay pubkey (32 bytes) + IPv4 (4 bytes) + port (2 bytes).
        # This is what peers decode to know where to send OBJECT_GET requests.
        provider_ip_bytes = socket.inet_aton(provider_ip)
        provider_port_bytes = int(provider_port).to_bytes(2, "big", signed=False)
        provider_key_bytes = self.config["relay_public_key_bytes"]
    except Exception as exc:
        node_logger.debug("Unable to encode provider info for %s: %s", expr_hex, exc)
        return False, f"unable to encode provider info: {exc}"

    provider_payload = provider_key_bytes + provider_ip_bytes + provider_port_bytes

    try:
        closest_peer = self.peer_route.closest_peer_for_hash(expr_id)
    except Exception as exc:
        node_logger.debug("Peer lookup failed for expr %s: %s", expr_hex, exc)
        return False, f"peer lookup failed: {exc}"

    is_self_closest = False
    if closest_peer is None or closest_peer.address is None:
        is_self_closest = True
    else:
        try:
            from ...communication.util import xor_distance
        except Exception as exc:
            node_logger.debug("Failed to import xor_distance for expr %s: %s", expr_hex, exc)
            is_self_closest = True
        else:
            try:
                self_distance = xor_distance(expr_id, self.config["relay_public_key_bytes"])
                peer_distance = xor_distance(expr_id, closest_peer.public_key_bytes)
            except Exception as exc:
                node_logger.debug("Failed computing distance for expr %s: %s", expr_hex, exc)
                is_self_closest = True
            else:
                is_self_closest = self_distance <= peer_distance

    if is_self_closest:
        node_logger.debug("Self is closest; indexing provider for expr %s", expr_hex)
        provider_id = provider_id_for_payload(self, provider_payload)
        self.storage_index[expr_id] = provider_id
        node_logger.debug("storage_index now has %d entries", len(self.storage_index))
        return True, None

    target_addr = closest_peer.address

    obj_req = ObjectRequest(
        code=ObjectRequestCode.OBJECT_PUT,
        data=provider_payload,
        atom_id=expr_id,
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
                "Advertised expr %s to peer at %s:%s",
                expr_hex,
                target_addr[0],
                target_addr[1],
            )
        else:
            node_logger.debug(
                "Dropped expr advertisement %s to peer at %s:%s",
                expr_hex,
                target_addr[0],
                target_addr[1],
            )
            return False, "enqueue_outgoing dropped advertisement"
    except Exception as exc:
        node_logger.debug(
            "Failed to queue advertisement for expr %s to %s:%s: %s",
            expr_hex,
            target_addr[0],
            target_addr[1],
            exc,
        )
        return False, f"failed to queue advertisement: {exc}"
    return True, None


def add_expr_advertisement(
    self,
    expr_id: bytes,
    payload_type: int,
    expires_at: float | None = None,
) -> None:
    """Track an expr id for periodic advertisement."""
    entry = (expr_id, payload_type, expires_at)
    with self.expr_advertisements_lock:
        self.expr_advertisements.append(entry)


def add_expr_advertisements(
    self,
    entries: Iterable[Tuple[bytes, int, float | None]],
) -> None:
    """Track multiple expr ids for periodic advertisement."""
    with self.expr_advertisements_lock:
        self.expr_advertisements.extend(entries)
