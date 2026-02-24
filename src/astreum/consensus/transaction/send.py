from __future__ import annotations

from .atomize import atomize_transaction
from .create import create_transaction


def send_transaction(
    node: "Node",
    receipient_public_key: bytes,
    sender_secret_key: bytes,
    amount: int,
) -> bytes:
    if not node.is_connected:
        raise RuntimeError("node not connected")

    latest_block = node.latest_block
    if latest_block is None:
        raise RuntimeError("latest block unavailable")

    import time
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from ...communication.handlers.object_response import OBJECT_FOUND_LIST_PAYLOAD
    from ...communication.models.message import Message, MessageTopic
    from ...communication.outgoing_queue import enqueue_outgoing
    from ...storage.advertisments import advertise_atoms
    from ...storage.cold.insert import insert_atom_into_cold_storage
    from ...storage.models.atom import ZERO32
    from ...validation.models.accounts import Accounts

    sender_key = Ed25519PrivateKey.from_private_bytes(bytes(sender_secret_key))
    sender_public_key_bytes = sender_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    accounts = Accounts(root_hash=getattr(latest_block, "accounts_hash", None))
    sender_account = accounts.get_account(address=sender_public_key_bytes, node=node)
    sender_counter = sender_account.counter if sender_account is not None else 0

    transaction = create_transaction(
        chain_id=int(node.config.get("chain_id", 0)),
        amount=int(amount),
        counter=sender_counter + 1,
        recipient=bytes(receipient_public_key),
        sender=sender_public_key_bytes,
    )
    body_head = transaction.sign(sender_key)
    tx_hash, atoms = atomize_transaction(transaction)

    for atom in atoms:
        atom_id = atom.object_id()
        node._hot_storage_set(atom_id, atom)
        insert_atom_into_cold_storage(node, atom)

    ttl_seconds = int(node.config["peer_timeout"])
    expires_at = time.time() + ttl_seconds if ttl_seconds > 0 else None
    entries = []
    for atom_id in (tx_hash, body_head):
        if atom_id and atom_id != ZERO32:
            entries.append((atom_id, OBJECT_FOUND_LIST_PAYLOAD, expires_at))
    if entries:
        node.add_atom_advertisements(entries)
        advertise_atoms(node, entries=entries)

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
                sender=node.relay_public_key,
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
            sender=node.relay_public_key,
        )
        tx_message.encrypt(peer.shared_key_bytes)
        enqueue_outgoing(
            node,
            peer.address,
            message=tx_message,
            difficulty=peer.difficulty,
        )

    return tx_hash
