from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ...communication.object_response.object_found import OBJECT_FOUND_LIST_PAYLOAD
from ...communication.models.message import Message, MessageTopic
from ...communication.outgoing_queue import enqueue_outgoing
from ...machine.models.expression import resolve_inner_exprs
from ...storage.advertisments import advertise_exprs
from ...storage.actions.set import _hot_storage_set
from ...storage.cold.insert import insert_expr_into_cold_storage
from ...machine.models.expression import ZERO32

if TYPE_CHECKING:
    from .model import Transaction


def send_transaction(
    node: "Node",
    transaction: "Transaction",
) -> bytes:
    """Atomize, store, advertise, and broadcast an already-signed Transaction.

    The caller must sign the transaction before calling this function:

        tx.sign(sender_key)
        send_transaction(node, tx)

    Returns the transaction's content-addressed hash (atom_hash).
    """
    if not node.is_connected:
        raise RuntimeError("node not connected")

    latest_block = node.latest_block
    if latest_block is None:
        raise RuntimeError("latest block unavailable")

    tx_hash = transaction.expr().hash()
    tx_exprs, _ = resolve_inner_exprs(node, transaction.expr())
    hot_store_failures = 0

    for tx_expr in tx_exprs:
        if not _hot_storage_set(node, tx_expr):
            hot_store_failures += 1
        insert_expr_into_cold_storage(node, tx_expr)

    if hot_store_failures:
        node.logger.warning(
            "Transaction hot storage writes skipped for tx %s: count=%s",
            tx_hash.hex(),
            hot_store_failures,
        )

    ttl_seconds = int(node.config["peer_timeout"])
    expires_at = time.time() + ttl_seconds if ttl_seconds > 0 else None
    entries = []
    body_hash = transaction.body_hash
    for atom_id in (tx_hash, body_hash):
        if atom_id and atom_id != ZERO32:
            entries.append((atom_id, OBJECT_FOUND_LIST_PAYLOAD, expires_at))
    if entries:
        node.add_atom_advertisements(entries)
        advertised_ids, advertise_warning = advertise_exprs(node, entries=entries)
        if advertise_warning:
            node.logger.warning(
                "Transaction advertisement batch had failures for tx %s: advertised=%s reason=%s",
                tx_hash.hex(),
                len(advertised_ids),
                advertise_warning,
            )

    validation_route = node.validation_route
    if validation_route is None:
        raise RuntimeError("no validator available")

    has_validators = bool(getattr(validation_route, "peers", None))
    if not has_validators:
        with node.peers_lock:
            peers = list(node.peers.items())

        for _peer_key, peer in peers:
            if not getattr(peer, "address", None):
                continue
            route_request = Message(
                topic=MessageTopic.ROUTE_REQUEST,
                content=b"\x01",
                sender_public_key_bytes=node.storage_public_key_bytes,
            )
            route_request.encrypt(peer.shared_key_bytes)
            enqueue_outgoing(
                node,
                peer.address,
                message=route_request,
                difficulty=peer.difficulty,
            )

        wait_deadline = time.time() + float(node.config.get("peer_timeout_interval", 10))
        while time.time() < wait_deadline:
            if getattr(validation_route, "peers", None):
                has_validators = True
                break
            time.sleep(0.1)

    if not has_validators:
        raise RuntimeError("no validator available")

    validators = {}
    for peer in validation_route.peers.values():
        if peer is not None and getattr(peer, "address", None):
            validators[getattr(peer, "public_key_bytes", None)] = peer
    for bucket in validation_route.buckets.values():
        for peer_key in bucket:
            peer = node.get_peer(peer_key)
            if peer is not None and getattr(peer, "address", None):
                validators[peer.public_key_bytes] = peer

    if not validators:
        raise RuntimeError("no validator available")

    for peer in validators.values():
        tx_message = Message(
            topic=MessageTopic.TRANSACTION,
            content=bytes(tx_hash),
            sender_public_key_bytes=node.storage_public_key_bytes,
        )
        tx_message.encrypt(peer.shared_key_bytes)
        enqueue_outgoing(
            node,
            peer.address,
            message=tx_message,
            difficulty=peer.difficulty,
        )

    return tx_hash
