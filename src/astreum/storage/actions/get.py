from __future__ import annotations

from time import sleep
from typing import List, Optional

from ...machine.models.expression import (
    Expr, ZERO32, RESOLUTION_SINGLE, RESOLUTION_LIST, RESOLUTION_FULL,
)
from ..cold.get import get_expr_from_cold_storage


def _hot_storage_get(self, key: bytes) -> Optional["Expr"]:
    """Retrieve an Expr from in-memory cache."""
    with self.hot_storage_lock:
        expr = self.hot_storage.get(key)
        if expr is not None:
            self.logger.debug("Hot storage hit for %s", key.hex())
        else:
            self.logger.debug("Hot storage miss for %s", key.hex())
        return expr


def get_expr_from_local_storage(node, expr_id: bytes) -> Optional["Expr"]:
    """Retrieve an Expr from local storage: hot → cold, no network."""
    with node.hot_storage_lock:
        expr = node.hot_storage.get(expr_id)
    if expr is not None:
        return expr
    return get_expr_from_cold_storage(node, expr_id)


def get_expr_list_from_local_storage(node, root_hash: bytes) -> Optional["Expr"]:
    """Walk an Expr link chain from local storage: hot → cold, no network."""
    if isinstance(root_hash, Expr):
        expr = root_hash
    else:
        expr = get_expr_from_local_storage(node, root_hash)
        if expr is None:
            return None

    current = expr
    while current is not None and current._tag == "link":
        if current._tail_hash is not None:
            resolved = get_expr_from_local_storage(node, current._tail_hash)
            if resolved is None:
                break
            current._tail = resolved
            current._tail_hash = None
        current = current._tail

    return expr


def get_expr_full_from_local_storage(node, root_hash: bytes) -> Optional["Expr"]:
    """Recursively resolve all inner hashes from local storage: hot → cold, no network."""
    if isinstance(root_hash, Expr):
        expr = root_hash
    else:
        expr = get_expr_from_local_storage(node, root_hash)
        if expr is None:
            return None
    if expr._tag != "link":
        return expr

    def _resolve(e: Expr) -> Expr:
        changed = True
        while changed:
            changed = False
            if e._tag != "link":
                break
            if e._head is None and e._head_hash is not None:
                head = get_expr_from_local_storage(node, e._head_hash)
                if head is not None:
                    e._head = _resolve(head)
                    e._head_hash = None
                    changed = True
            if e._tail is None and e._tail_hash is not None:
                tail = get_expr_from_local_storage(node, e._tail_hash)
                if tail is not None:
                    e._tail = _resolve(tail)
                    e._tail_hash = None
                    changed = True
        return e

    return _resolve(expr)


def _collect_missing_hashes(expr: "Expr", resolution: int) -> list[bytes]:
    """Return unresolved hashes from a partially-resolved expr."""
    missing: list[bytes] = []
    if resolution == RESOLUTION_LIST:
        current = expr
        while current is not None and current._tag == "link":
            if current._tail_hash is not None:
                missing.append(current._tail_hash)
                break
            current = current._tail
    elif resolution == RESOLUTION_FULL:
        stack = [expr]
        while stack:
            e = stack.pop()
            if e._tag != "link":
                continue
            if e._head is not None:
                stack.append(e._head)
            elif e._head_hash is not None:
                missing.append(e._head_hash)
            if e._tail is not None:
                stack.append(e._tail)
            elif e._tail_hash is not None:
                missing.append(e._tail_hash)
    return missing


def _send_object_request(node, expr_id: bytes, resolution: int) -> Optional[str]:
    """Send an OBJECT_GET request to a peer. Returns error string or None."""
    from ...communication.object_request.code import ObjectRequestCode
    from ...communication.object_request.model import ObjectRequest
    from ...communication.models.message import Message, MessageTopic
    from ...communication.outgoing_queue import enqueue_outgoing

    provider_id = node.storage_index.get(expr_id)
    if provider_id is not None:
        from ..providers import provider_payload_for_id
        from ...communication.object_response.object_provider import decode_object_provider
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

        provider_payload = provider_payload_for_id(node, provider_id)
        if provider_payload is not None:
            try:
                storage_key_bytes, relay_key_bytes, provider_address, provider_port = decode_object_provider(provider_payload)
                provider_public_key = X25519PublicKey.from_public_bytes(relay_key_bytes)
                shared_key_bytes = node.relay_secret_key.exchange(provider_public_key)

                obj_req = ObjectRequest(
                    code=ObjectRequestCode.OBJECT_GET,
                    data=b"",
                    atom_id=expr_id,
                    payload_type=resolution,
                )
                message = Message(
                    topic=MessageTopic.OBJECT_REQUEST,
                    content=obj_req.to_bytes(),
                    sender_public_key_bytes=node.storage_public_key_bytes,
                )
                message.encrypt(shared_key_bytes)
                node.add_expr_req(expr_id, resolution)
                queued = enqueue_outgoing(
                    node,
                    (provider_address, provider_port),
                    message=message,
                    difficulty=1,
                )
                if queued:
                    node.logger.debug(
                        "Requested %s %s from indexed provider %s:%s",
                        resolution,
                        expr_id.hex(),
                        provider_address,
                        provider_port,
                    )
                else:
                    node.logger.debug(
                        "Dropped request for %s %s to indexed provider %s:%s",
                        resolution,
                        expr_id.hex(),
                        provider_address,
                        provider_port,
                    )
                return None
            except Exception as exc:
                node.logger.debug("Failed indexed fetch for %s: %s", expr_id.hex(), exc)
                return f"failed indexed fetch: {exc}"
        return f"unknown provider id {provider_id}"

    try:
        closest_peer = node.peer_route.closest_peer_for_hash(expr_id)
    except Exception as exc:
        return f"peer lookup failed: {exc}"

    if closest_peer is None or closest_peer.address is None:
        return "no peer available"

    obj_req = ObjectRequest(
        code=ObjectRequestCode.OBJECT_GET,
        data=b"",
        atom_id=expr_id,
        payload_type=resolution,
    )
    try:
        message = Message(
            topic=MessageTopic.OBJECT_REQUEST,
            content=obj_req.to_bytes(),
            sender_public_key_bytes=node.storage_public_key_bytes,
        )
    except Exception as exc:
        return f"failed to build object request: {exc}"

    message.encrypt(closest_peer.shared_key_bytes)
    node.add_expr_req(expr_id, resolution)

    try:
        queued = enqueue_outgoing(
            node,
            closest_peer.address,
            message=message,
            difficulty=closest_peer.difficulty,
        )
        if queued:
            node.logger.debug(
                "Queued OBJECT_GET %s for %s to peer %s",
                resolution,
                expr_id.hex(),
                closest_peer.address,
            )
        else:
            node.logger.debug(
                "Dropped OBJECT_GET %s for %s to peer %s",
                resolution,
                expr_id.hex(),
                closest_peer.address,
            )
    except Exception as exc:
        return f"failed to queue OBJECT_GET: {exc}"
    return None


def get_expr_from_network(node, expr_id: bytes, resolution: int = RESOLUTION_SINGLE) -> Optional["Expr"]:
    """Send an OBJECT_GET request and wait for the response.

    For RESOLUTION_LIST: polls list resolution, retries missing tail hashes.
    For RESOLUTION_FULL: polls full resolution, retries missing inner hashes.
    For RESOLUTION_SINGLE: polls single expr appearance.
    """
    if not node.is_connected:
        node.logger.debug("Network fetch skipped for %s; node not connected", expr_id.hex())
        return None

    node.logger.debug("Attempting network fetch for %s (resolution=%s)", expr_id.hex(), resolution)

    err = _send_object_request(node, expr_id, resolution)
    if err is not None:
        node.logger.debug("Network request failed for %s: %s", expr_id.hex(), err)
        return None

    interval = node.config["expr_fetch_interval"]
    retries = node.config["expr_fetch_retries"]

    def _poll_single() -> Optional[Expr]:
        if interval <= 0 or retries <= 0:
            return get_expr_from_local_storage(node, expr_id)
        for _ in range(retries):
            expr = get_expr_from_local_storage(node, expr_id)
            if expr is not None:
                return expr
            sleep(interval)
        return get_expr_from_local_storage(node, expr_id)

    def _poll_list() -> Optional[Expr]:
        for attempt in range(max(retries, 1)):
            raw = get_expr_list_from_local_storage(node, expr_id)
            if raw is not None:
                missing = _collect_missing_hashes(raw, RESOLUTION_LIST)
                if not missing:
                    return raw
                for h in missing:
                    get_expr_from_network(node, h, RESOLUTION_SINGLE)
            else:
                sleep(interval)
        return get_expr_list_from_local_storage(node, expr_id)

    def _poll_full() -> Optional[Expr]:
        for attempt in range(max(retries, 1)):
            raw = get_expr_full_from_local_storage(node, expr_id)
            if raw is not None:
                missing = _collect_missing_hashes(raw, RESOLUTION_FULL)
                if not missing:
                    return raw
                for h in missing:
                    get_expr_from_network(node, h, RESOLUTION_SINGLE)
            else:
                sleep(interval)
        return get_expr_full_from_local_storage(node, expr_id)

    if resolution == RESOLUTION_LIST:
        return _poll_list()
    if resolution == RESOLUTION_FULL:
        return _poll_full()
    return _poll_single()


def get_expr(node, expr_id: bytes) -> Optional["Expr"]:
    """Retrieve an Expr: hot → cold → network. Returns shallow (hash refs)."""
    with node.hot_storage_lock:
        expr = node.hot_storage.get(expr_id)
    if expr is not None:
        return expr

    expr = get_expr_from_cold_storage(node, expr_id)
    if expr is not None:
        return expr

    expr = get_expr_from_network(node, expr_id, RESOLUTION_SINGLE)
    if expr is not None:
        return expr

    return None


def get_expr_full(node, expr_id: bytes) -> Optional["Expr"]:
    """Retrieve an Expr with all inner hashes resolved inline."""
    expr = get_expr(node, expr_id)
    if expr is None:
        return None
    if not expr._tag == "link":
        return expr

    if expr._head is None and expr._head_hash is not None:
        head = get_expr_full(node, expr._head_hash)
        if head is None:
            return None
        expr._head = head
        expr._head_hash = None

    if expr._tail is None and expr._tail_hash is not None:
        tail = get_expr_full(node, expr._tail_hash)
        if tail is None:
            return None
        expr._tail = tail
        expr._tail_hash = None

    return expr


def get_expr_list(node, root_hash: bytes) -> Optional["Expr"]:
    """Retrieve an Expr list: get_expr + walk tail chain."""
    if isinstance(root_hash, Expr):
        expr = root_hash
    else:
        expr = get_expr(node, root_hash)
        if expr is None:
            return None

    current = expr
    while current is not None and current._tag == "link":
        if current._tail_hash is not None:
            resolved = get_expr(node, current._tail_hash)
            if resolved is None:
                return None
            current._tail = resolved
            current._tail_hash = None
        current = current._tail
    return expr
