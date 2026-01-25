from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

from ..outgoing_queue import enqueue_outgoing
from ..models.peer import Peer
from ..models.message import Message, MessageTopic
from ..models.ping import Ping
from ..difficulty import message_difficulty

if TYPE_CHECKING:
    from .... import Node


def handle_handshake(node: "Node", addr: Sequence[object], message: Message) -> bool:
    """Handle incoming handshake messages.

    Returns True if the outer loop should `continue`, False otherwise.
    """
    def _queue_handshake_ping(peer: Peer, peer_address: tuple[str, int]) -> None:
        latest_block = getattr(node, "latest_block_hash", None)
        if not isinstance(latest_block, (bytes, bytearray)) or len(latest_block) != 32:
            latest_block = None
        try:
            ping_payload = Ping(
                is_validator=bool(getattr(node, "validation_public_key", None)),
                difficulty=message_difficulty(node),
                latest_block=latest_block,
            ).to_bytes()
            ping_msg = Message(
                topic=MessageTopic.PING,
                content=ping_payload,
                sender=node.relay_public_key,
            )
            ping_msg.encrypt(peer.shared_key_bytes)
            enqueue_outgoing(
                node,
                peer_address,
                message=ping_msg,
                difficulty=peer.difficulty,
            )
        except Exception as exc:
            node.logger.debug(
                "Failed sending handshake ping to %s:%s: %s",
                peer_address[0],
                peer_address[1],
                exc,
            )
    sender_public_key_bytes = message.sender_public_key_bytes
    try:
        sender_key = X25519PublicKey.from_public_bytes(sender_public_key_bytes)
    except Exception as exc:
        node.logger.warning("Error extracting sender key bytes: %s", exc)
        return True

    try:
        host = addr[0]
    except Exception:
        return True

    if message.incoming_port is None:
        node.logger.warning("Handshake missing incoming_port")
        return True
    
    port = message.incoming_port
    peer_address = (host, port)
    default_seed_ips = getattr(node, "default_seed_ips", None)
    is_default_seed = bool(default_seed_ips) and host in default_seed_ips

    existing_peer = node.get_peer(sender_public_key_bytes)
    if existing_peer is not None:
        existing_peer.address = peer_address
        existing_peer.is_default_seed = is_default_seed
        _queue_handshake_ping(existing_peer, peer_address)
        return False

    try:
        peer = Peer(
            node_secret_key=node.relay_secret_key,
            peer_public_key=sender_key,
            address=peer_address,
            is_default_seed=is_default_seed,
        )
    except Exception:
        return True

    node.add_peer(sender_public_key_bytes, peer)
    node.peer_route.add_peer(sender_public_key_bytes, peer)

    node.logger.info(
        "Handshake accepted from %s:%s; peer added",
        peer_address[0],
        peer_address[1],
    )
    response = Message(
        handshake=True,
        sender=node.relay_public_key,
        incoming_port=node.config["incoming_port"],
        content=b"",
    )
    enqueue_outgoing(
        node,
        peer_address,
        message=response,
        difficulty=peer.difficulty,
    )
    _queue_handshake_ping(peer, peer_address)
    return True
