from __future__ import annotations

from time import sleep
from typing import List, Optional, Union

from ...machine.models.expression import Expr, ZERO32
from ..providers import provider_payload_for_id
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


def _get_expr_from_local_storage(self, expr_id: bytes) -> Optional["Expr"]:
    """Retrieve an Expr from local storage: hot → cold, no network."""
    expr = _hot_storage_get(self, expr_id)
    if expr is not None:
        return expr
    expr = get_expr_from_cold_storage(self, expr_id)
    # if expr is not None:
    #     from ...storage.actions.set import _hot_storage_set
    #     _hot_storage_set(self, expr)
    return expr


def get_expr(self, expr_id: bytes) -> Optional["Expr"]:
    """Retrieve an Expr: hot → cold → network."""
    from ...machine.models.expression import Expr
    from ...storage.cold.get import get_expr_from_cold_storage
    # from ...storage.actions.set import _hot_storage_set

    with self.hot_storage_lock:
        expr = self.hot_storage.get(expr_id)
    if expr is not None:
        return expr

    expr = get_expr_from_cold_storage(self, expr_id)
    if expr is not None:
        # _hot_storage_set(self, expr)
        return expr

    expr = _network_get_expr(self, expr_id)
    if expr is not None:
        return expr

    return None


def get_expr_full(self, expr_id: bytes) -> Optional["Expr"]:
    from ...machine.models.expression import Expr

    expr = self.get_expr(expr_id)
    if expr is None:
        return None
    if not isinstance(expr, Expr.Link):
        return expr

    if expr.head is None and expr.head_hash is not None:
        head = self.get_expr_full(expr.head_hash)
        if head is None:
            return None
        expr.head = head
        expr.head_hash = None

    if expr.tail is None and expr.tail_hash is not None:
        tail = self.get_expr_full(expr.tail_hash)
        if tail is None:
            return None
        expr.tail = tail
        expr.tail_hash = None

    return expr


def _network_get(
    self, atom_id: bytes, payload_type: int
) -> tuple[Optional[Union[Expr, List[Expr]]], Optional[str]]:
    """Attempt to fetch an atom from network peers when local storage misses."""
    from ...communication.object_response.object_found import (
        OBJECT_FOUND_ATOM_PAYLOAD,
        OBJECT_FOUND_LIST_PAYLOAD,
    )
    from ...machine.models.expression import resolve_list_exprs

    def _wait_for_atom(atom_id: bytes, interval: float, retries: int) -> Optional[Expr]:
        if interval <= 0 or retries <= 0:
            return _get_expr_from_local_storage(self, atom_id)
        for _ in range(retries):
            atom = _get_expr_from_local_storage(self, atom_id)
            if atom is not None:
                return atom
            sleep(interval)
        return _get_expr_from_local_storage(self, atom_id)

    def _wait_for_list(root_hash: bytes, interval: float, retries: int) -> Optional[List[Expr]]:
        if interval <= 0 or retries <= 0:
            raw = self.get_expr_list_from_local_storage(root_hash=root_hash)
            if raw is None:
                return None
            items, _ = resolve_list_exprs(self, raw)
            return items
        for _ in range(retries):
            raw = self.get_expr_list_from_local_storage(root_hash=root_hash)
            if raw is not None:
                items, _ = resolve_list_exprs(self, raw)
                return items
            sleep(interval)
        raw = self.get_expr_list_from_local_storage(root_hash=root_hash)
        if raw is None:
            return None
        items, _ = resolve_list_exprs(self, raw)
        return items

    def _wait_for_payload() -> tuple[Optional[Union[Expr, List[Expr]]], Optional[str]]:
        wait_interval = self.config["expr_fetch_interval"]
        wait_retries = self.config["expr_fetch_retries"]
        if payload_type == OBJECT_FOUND_ATOM_PAYLOAD:
            return _wait_for_atom(atom_id, wait_interval, wait_retries), None
        if payload_type == OBJECT_FOUND_LIST_PAYLOAD:
            return _wait_for_list(atom_id, wait_interval, wait_retries), None
        self.logger.debug(
            "Unknown payload type %s for %s",
            payload_type,
            atom_id.hex(),
        )
        return None, f"unknown payload type {payload_type}"

    if payload_type == OBJECT_FOUND_ATOM_PAYLOAD:
        local_atom = _get_expr_from_local_storage(self, atom_id)
        if local_atom is not None:
            return local_atom, None
    elif payload_type == OBJECT_FOUND_LIST_PAYLOAD:
        raw_atoms = self.get_expr_list_from_local_storage(root_hash=atom_id)
        if raw_atoms is not None:
            items, _ = resolve_list_exprs(self, raw_atoms)
            return items, None
    else:
        self.logger.debug(
            "Unknown payload type %s for %s",
            payload_type,
            atom_id.hex(),
        )
        return None, f"unknown payload type {payload_type}"

    if not self.is_connected:
        self.logger.debug("Network fetch skipped for %s; node not connected", atom_id.hex())
        return None, "node not connected"
    self.logger.debug("Attempting network fetch for %s", atom_id.hex())
    
    provider_id = self.storage_index.get(atom_id)
    if provider_id is not None:
        provider_payload = provider_payload_for_id(self, provider_id)
        if provider_payload is not None:
            try:
                from ...communication.object_response.object_provider import decode_object_provider
                from ...communication.object_request.code import ObjectRequestCode
                from ...communication.object_request.model import ObjectRequest
                from ...communication.models.message import Message, MessageTopic
                from ...communication.outgoing_queue import enqueue_outgoing
                from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

                storage_key_bytes, relay_key_bytes, provider_address, provider_port = decode_object_provider(provider_payload)
                provider_public_key = X25519PublicKey.from_public_bytes(relay_key_bytes)
                shared_key_bytes = self.relay_secret_key.exchange(provider_public_key)

                obj_req = ObjectRequest(
                    code=ObjectRequestCode.OBJECT_GET,
                    data=b"",
                    atom_id=atom_id,
                    payload_type=payload_type,
                )
                message = Message(
                    topic=MessageTopic.OBJECT_GET,
                    content=obj_req.to_bytes(),
                    sender_public_key_bytes=self.storage_public_key_bytes,
                )
                message.encrypt(shared_key_bytes)
                self.add_expr_req(atom_id, payload_type)
                queued = enqueue_outgoing(
                    self,
                    (provider_address, provider_port),
                    message=message,
                    difficulty=1,
                )
                if queued:
                    self.logger.debug(
                        "Requested atom %s from indexed provider %s:%s",
                        atom_id.hex(),
                        provider_address,
                        provider_port,
                    )
                else:
                    self.logger.debug(
                        "Dropped request for atom %s to indexed provider %s:%s",
                        atom_id.hex(),
                        provider_address,
                        provider_port,
                    )
            except Exception as exc:
                self.logger.debug("Failed indexed fetch for %s: %s", atom_id.hex(), exc)
                return _wait_for_payload()[0], f"failed indexed fetch: {exc}"
            return _wait_for_payload()
        self.logger.debug("Unknown provider id %s for %s", provider_id, atom_id.hex())
        return None, f"unknown provider id {provider_id}"

    self.logger.debug("Falling back to network fetch for %s", atom_id.hex())

    from ...communication.object_request.code import ObjectRequestCode
    from ...communication.object_request.model import ObjectRequest
    from ...communication.models.message import Message, MessageTopic
    from ...communication.outgoing_queue import enqueue_outgoing

    try:
        closest_peer = self.peer_route.closest_peer_for_hash(atom_id)
    except Exception as exc:
        self.logger.debug("Peer lookup failed for %s: %s", atom_id.hex(), exc)
        result, _ = _wait_for_payload()
        return result, f"peer lookup failed: {exc}"

    if closest_peer is None or closest_peer.address is None:
        self.logger.debug("No peer available to fetch %s", atom_id.hex())
        return None, "no peer available"

    obj_req = ObjectRequest(
        code=ObjectRequestCode.OBJECT_GET,
        data=b"",
        atom_id=atom_id,
        payload_type=payload_type,
    )
    try:
        message = Message(
            topic=MessageTopic.OBJECT_REQUEST,
            content=obj_req.to_bytes(),
            sender_public_key_bytes=self.storage_public_key_bytes,
        )
    except Exception as exc:
        self.logger.debug("Failed to build object request for %s: %s", atom_id.hex(), exc)
        return None, f"failed to build object request: {exc}"

    # encrypt the outbound request for the target peer
    message.encrypt(closest_peer.shared_key_bytes)

    try:
        self.add_expr_req(atom_id, payload_type)
    except Exception as exc:
        self.logger.debug("Failed to track object request for %s: %s", atom_id.hex(), exc)
        return None, f"failed to track object request: {exc}"

    try:
        queued = enqueue_outgoing(
            self,
            closest_peer.address,
            message=message,
            difficulty=closest_peer.difficulty,
        )
        if queued:
            self.logger.debug(
                "Queued OBJECT_GET for %s to peer %s",
                atom_id.hex(),
                closest_peer.address,
            )
        else:
            self.logger.debug(
                "Dropped OBJECT_GET for %s to peer %s",
                atom_id.hex(),
                closest_peer.address,
            )
    except Exception as exc:
        self.logger.debug(
            "Failed to queue OBJECT_GET for %s to %s: %s",
            atom_id.hex(),
            closest_peer.address,
            exc,
        )
        return None, f"failed to queue OBJECT_GET: {exc}"
    result, _ = _wait_for_payload()
    return result, None


def get_expr_list_from_local_storage(self, root_hash: bytes) -> Optional["Expr"]:
    """Walk an Expr Link chain from local storage, resolving tail hashes.

    Accepts either a bytes hash to look up, or an already-resolved Expr
    (e.g. the value returned by ``Trie.get``), in which case it is walked
    directly. This keeps retrieval consistent with trie values that are
    stored as hashes but resolved to Exprs on read.
    """
    from ...machine.models.expression import Expr

    if isinstance(root_hash, (Expr.Link, Expr.Bytes, Expr.Symbol,
                              Expr.Int, Expr.Float, Expr.String)):
        expr = root_hash
    else:
        expr = _hot_storage_get(self, root_hash)
        if expr is None:
            expr = get_expr_from_cold_storage(self, root_hash)
            if expr is None:
                return None

    current = expr
    while isinstance(current, Expr.Link):
        if current.tail_hash is not None:
            resolved = _hot_storage_get(self, current.tail_hash)
            if resolved is None:
                resolved = get_expr_from_cold_storage(self, current.tail_hash)
            if resolved is not None:
                current.tail = resolved
                current.tail_hash = None
        current = current.tail

    return expr


def _network_get_expr(self, expr_id: bytes) -> Optional["Expr"]:
    """Attempt to fetch an Expr from network peers when local storage misses."""
    from ...machine.models.expression import Expr
    from ...communication.object_response.object_found import (
        OBJECT_FOUND_ATOM_PAYLOAD,
    )

    def _wait_for_expr(eid: bytes, interval: float, retries: int) -> Optional[Expr]:
        if interval <= 0 or retries <= 0:
            return _hot_storage_get(self, eid)
        for _ in range(retries):
            expr = _hot_storage_get(self, eid)
            if expr is not None:
                return expr
            sleep(interval)
        return _hot_storage_get(self, eid)

    if not self.is_connected:
        self.logger.debug("Network expr fetch skipped for %s; node not connected", expr_id.hex())
        return None
    self.logger.debug("Attempting network expr fetch for %s", expr_id.hex())

    provider_id = self.storage_index.get(expr_id)
    if provider_id is not None:
        provider_payload = provider_payload_for_id(self, provider_id)
        if provider_payload is not None:
            try:
                from ...communication.object_response.object_provider import decode_object_provider
                from ...communication.object_request.code import ObjectRequestCode
                from ...communication.object_request.model import ObjectRequest
                from ...communication.models.message import Message, MessageTopic
                from ...communication.outgoing_queue import enqueue_outgoing
                from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

                storage_key_bytes, relay_key_bytes, provider_address, provider_port = decode_object_provider(provider_payload)
                provider_public_key = X25519PublicKey.from_public_bytes(relay_key_bytes)
                shared_key_bytes = self.relay_secret_key.exchange(provider_public_key)

                obj_req = ObjectRequest(
                    code=ObjectRequestCode.OBJECT_GET,
                    data=b"",
                    atom_id=expr_id,
                    payload_type=OBJECT_FOUND_ATOM_PAYLOAD,
                )
                message = Message(
                    topic=MessageTopic.OBJECT_REQUEST,
                    content=obj_req.to_bytes(),
                    sender_public_key_bytes=self.storage_public_key_bytes,
                )
                message.encrypt(shared_key_bytes)
                self.add_expr_req(expr_id, OBJECT_FOUND_ATOM_PAYLOAD)
                queued = enqueue_outgoing(
                    self,
                    (provider_address, provider_port),
                    message=message,
                    difficulty=1,
                )
                if queued:
                    self.logger.debug(
                        "Requested expr %s from indexed provider %s:%s",
                        expr_id.hex(),
                        provider_address,
                        provider_port,
                    )
                else:
                    self.logger.debug(
                        "Dropped request for expr %s to indexed provider %s:%s",
                        expr_id.hex(),
                        provider_address,
                        provider_port,
                    )
            except Exception as exc:
                self.logger.debug("Failed indexed fetch for expr %s: %s", expr_id.hex(), exc)
                return _wait_for_expr(expr_id, self.config["expr_fetch_interval"], self.config["expr_fetch_retries"])
            return _wait_for_expr(expr_id, self.config["expr_fetch_interval"], self.config["expr_fetch_retries"])
        self.logger.debug("Unknown provider id %s for expr %s", provider_id, expr_id.hex())
        return None

    self.logger.debug("Falling back to network expr fetch for %s", expr_id.hex())

    from ...communication.object_request.code import ObjectRequestCode
    from ...communication.object_request.model import ObjectRequest
    from ...communication.models.message import Message, MessageTopic
    from ...communication.outgoing_queue import enqueue_outgoing

    try:
        closest_peer = self.peer_route.closest_peer_for_hash(expr_id)
    except Exception as exc:
        self.logger.debug("Peer lookup failed for expr %s: %s", expr_id.hex(), exc)
        return _wait_for_expr(expr_id, self.config["expr_fetch_interval"], self.config["expr_fetch_retries"])

    if closest_peer is None or closest_peer.address is None:
        self.logger.debug("No peer available to fetch expr %s", expr_id.hex())
        return None

    obj_req = ObjectRequest(
        code=ObjectRequestCode.OBJECT_GET,
        data=b"",
        atom_id=expr_id,
        payload_type=OBJECT_FOUND_ATOM_PAYLOAD,
    )
    try:
        message = Message(
            topic=MessageTopic.OBJECT_REQUEST,
            content=obj_req.to_bytes(),
            sender_public_key_bytes=self.storage_public_key_bytes,
        )
    except Exception as exc:
        self.logger.debug("Failed to build object request for expr %s: %s", expr_id.hex(), exc)
        return None

    message.encrypt(closest_peer.shared_key_bytes)

    try:
        self.add_expr_req(expr_id, OBJECT_FOUND_ATOM_PAYLOAD)
    except Exception as exc:
        self.logger.debug("Failed to track object request for expr %s: %s", expr_id.hex(), exc)
        return None

    try:
        queued = enqueue_outgoing(
            self,
            closest_peer.address,
            message=message,
            difficulty=closest_peer.difficulty,
        )
        if queued:
            self.logger.debug(
                "Queued OBJECT_GET for expr %s to peer %s",
                expr_id.hex(),
                closest_peer.address,
            )
        else:
            self.logger.debug(
                "Dropped OBJECT_GET for expr %s to peer %s",
                expr_id.hex(),
                closest_peer.address,
            )
    except Exception as exc:
        self.logger.debug(
            "Failed to queue OBJECT_GET for expr %s to %s: %s",
            expr_id.hex(),
            closest_peer.address,
            exc,
        )
        return None
    return _wait_for_expr(expr_id, self.config["expr_fetch_interval"], self.config["expr_fetch_retries"])


def _network_get_expr_list(self, root_hash: bytes) -> Optional["Expr"]:
    """Attempt to fetch an Expr list from network peers."""
    from ...communication.object_response.object_found import (
        OBJECT_FOUND_LIST_PAYLOAD,
    )

    def _wait_for_list(rh: bytes, interval: float, retries: int) -> Optional["Expr"]:
        if interval <= 0 or retries <= 0:
            return get_expr_list_from_local_storage(self, rh)
        for _ in range(retries):
            expr = get_expr_list_from_local_storage(self, rh)
            if expr is not None:
                return expr
            sleep(interval)
        return get_expr_list_from_local_storage(self, rh)

    if not self.is_connected:
        return None

    from ...communication.object_request.code import ObjectRequestCode
    from ...communication.object_request.model import ObjectRequest
    from ...communication.models.message import Message, MessageTopic
    from ...communication.outgoing_queue import enqueue_outgoing

    try:
        closest_peer = self.peer_route.closest_peer_for_hash(root_hash)
    except Exception:
        return _wait_for_list(root_hash, self.config["expr_fetch_interval"], self.config["expr_fetch_retries"])

    if closest_peer is None or closest_peer.address is None:
        return None

    obj_req = ObjectRequest(
        code=ObjectRequestCode.OBJECT_GET,
        data=b"",
        atom_id=root_hash,
        payload_type=OBJECT_FOUND_LIST_PAYLOAD,
    )
    try:
        message = Message(
            topic=MessageTopic.OBJECT_REQUEST,
            content=obj_req.to_bytes(),
            sender_public_key_bytes=self.storage_public_key_bytes,
        )
    except Exception:
        return None

    message.encrypt(closest_peer.shared_key_bytes)

    try:
        self.add_expr_req(root_hash, OBJECT_FOUND_LIST_PAYLOAD)
    except Exception:
        return None

    try:
        enqueue_outgoing(self, closest_peer.address, message=message, difficulty=closest_peer.difficulty)
    except Exception:
        return None

    return _wait_for_list(root_hash, self.config["expr_fetch_interval"], self.config["expr_fetch_retries"])


def get_expr_list(self, root_hash: bytes) -> Optional["Expr"]:
    """Retrieve an Expr list: local → network."""
    expr = get_expr_list_from_local_storage(self, root_hash)
    if expr is not None:
        return expr
    return _network_get_expr_list(self, root_hash)


def get_atom_list(self, root_hash: bytes) -> Optional[List[Expr]]:
    """Retrieve an atom list locally first, then request it from the network."""
    from ...machine.models.expression import resolve_list_exprs

    raw = self.get_expr_list_from_local_storage(root_hash=root_hash)
    if raw is not None:
        items, _ = resolve_list_exprs(self, raw)
        return items
    from ...communication.object_response.object_found import OBJECT_FOUND_LIST_PAYLOAD

    self.logger.debug(
        "Local list miss for %s; requesting from network",
        root_hash.hex(),
    )
    result, reason = self._network_get(root_hash, OBJECT_FOUND_LIST_PAYLOAD)
    if isinstance(result, list):
        return result
    self.logger.warning(
        "Network fetch returned no list for %s: %s",
        root_hash.hex(),
        reason or "no result",
    )
    return None
