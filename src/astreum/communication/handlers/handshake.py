from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

from ..models.peer import Peer
from ..models.message import Message

if TYPE_CHECKING:
    from .... import Node


def handle_handshake(node: "Node", addr: Sequence[object], message: Message) -> bool:
    """Handle incoming handshake messages.

    Returns True if the outer loop should `continue`, False otherwise.
    """
    logger = node.logger

    sender_public_key_bytes = message.sender_bytes
    try:
        sender_key = X25519PublicKey.from_public_bytes(sender_public_key_bytes)
    except Exception as exc:
        logger.warning("Error extracting sender key bytes: %s", exc)
        return True

    try:
        host, port = addr[0], int(addr[1])
    except Exception:
        return True
    address_key = (host, port)

    old_key_bytes = node.addresses.get(address_key)
    node.addresses[address_key] = sender_public_key_bytes

    if old_key_bytes is None:
        try:
            peer = Peer(node.relay_secret_key, sender_key)
        except Exception:
            return True
        peer.address = address_key

        node.peers[sender_public_key_bytes] = peer
        node.peer_route.add_peer(sender_public_key_bytes, peer)

        logger.info(
            "Handshake accepted from %s:%s; peer added",
            address_key[0],
            address_key[1],
        )
        response = Message(handshake=True, sender=node.relay_public_key)
        node.outgoing_queue.put((response.to_bytes(), address_key))
        return True

    if old_key_bytes == sender_public_key_bytes:
        peer = node.peers.get(sender_public_key_bytes)
        if peer is not None:
            peer.address = address_key
        return False

    node.peers.pop(old_key_bytes, None)
    try:
        node.peer_route.remove_peer(old_key_bytes)
    except Exception:
        pass
    try:
        peer = Peer(node.relay_secret_key, sender_key)
    except Exception:
        return True
    peer.address = address_key

    node.peers[sender_public_key_bytes] = peer
    node.peer_route.add_peer(sender_public_key_bytes, peer)
    logger.info(
        "Peer at %s:%s replaced due to key change",
        address_key[0],
        address_key[1],
    )
    return False
