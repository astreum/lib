from __future__ import annotations

import socket
from queue import Empty
from typing import TYPE_CHECKING

from ..handlers.handshake import handle_handshake
from ..handlers.object_request import handle_object_request
from ..handlers.object_response import handle_object_response
from ..handlers.ping import handle_ping
from ..handlers.route_request import handle_route_request
from ..handlers.route_response import handle_route_response
from ..incoming_queue import enqueue_incoming
from ..models.message import Message, MessageTopic
from ..models.peer import Peer
from ..outgoing_queue import enqueue_outgoing
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

if TYPE_CHECKING:
    from .. import Node


def process_incoming_messages(node: "Node") -> None:
    """Process incoming messages (placeholder)."""
    stop = getattr(node, "communication_stop_event", None)
    while stop is None or not stop.is_set():
        try:
            item = node.incoming_queue.get(timeout=0.5)
        except Empty:
            continue
        except Exception:
            node.logger.exception("Error taking from incoming queue")
            continue

        data = None
        addr = None
        accounted_size = None

        if isinstance(item, tuple) and len(item) == 3:
            data, addr, accounted_size = item
        else:
            node.logger.warning("Incoming queue item has unexpected shape: %r", item)
            continue

        if stop is not None and stop.is_set():
            if accounted_size is not None:
                try:
                    with node.incoming_queue_size_lock:
                        node.incoming_queue_size = max(0, node.incoming_queue_size - int(accounted_size))
                except Exception:
                    node.logger.exception("Failed updating incoming_queue_size on shutdown")
            break

        try:
            message = Message.from_bytes(data)
        except Exception as exc:
            node.logger.warning("Error decoding message: %s", exc)
            continue

        if message.handshake:
            if handle_handshake(node, addr, message):
                continue

        if message.incoming_port is None:
            node.logger.warning("Message from %s missing incoming_port header; dropping", addr)
            continue

        peer = None
        try:
            peer = node.get_peer(message.sender_public_key_bytes)
        except Exception:
            peer = None

        if peer is None:
            try:
                peer_key = X25519PublicKey.from_public_bytes(message.sender_public_key_bytes)
                host = addr[0]
                port = message.incoming_port
                default_seed_ips = getattr(node, "default_seed_ips", None)
                is_default_seed = bool(default_seed_ips) and host in default_seed_ips
                peer = Peer(
                    node_secret_key=node.relay_secret_key,
                    peer_public_key=peer_key,
                    address=(host, port),
                    is_default_seed=is_default_seed,
                )
            except Exception:
                peer = None
        else:
            peer_address = (addr[0], message.incoming_port)
            if peer.address != peer_address:
                peer.address = peer_address

        if peer is None:
            node.logger.debug("Unable to resolve peer for message from %s", addr)
            continue

        # decrypt message payload before dispatch
        try:
            message.decrypt(peer.shared_key_bytes)
        except Exception as exc:
            node.logger.warning(
                "Error decrypting message from %s (len=%s, enc_len=%s, exc=%s)",
                peer.address,
                len(data),
                len(message.encrypted) if message.encrypted is not None else None,
                exc,
            )
            try:
                host = addr[0]
                port = message.incoming_port
                handshake_message = Message(
                    handshake=True,
                    sender=node.relay_public_key,
                    content=int(node.config["incoming_port"]).to_bytes(2, "big", signed=False),
                )
                enqueue_outgoing(
                    node,
                    (host, port),
                    message=handshake_message,
                    difficulty=1,
                )
            except Exception as handshake_exc:
                node.logger.debug(
                    "Failed queueing rekey handshake to %s: %s",
                    addr,
                    handshake_exc,
                )
            continue

        try:
            match message.topic:
                case MessageTopic.PING:
                    handle_ping(node, peer, message.content)

                case MessageTopic.OBJECT_REQUEST:
                    handle_object_request(node, peer, message)

                case MessageTopic.OBJECT_RESPONSE:
                    handle_object_response(node, peer, message)

                case MessageTopic.ROUTE_REQUEST:
                    handle_route_request(node, peer, message)

                case MessageTopic.ROUTE_RESPONSE:
                    handle_route_response(node, peer, message)

                case MessageTopic.TRANSACTION:
                    if node.validation_secret_key is None:
                        continue
                    node._validation_transaction_queue.put(message.content)

                case _:
                    continue
        finally:
            if accounted_size is not None:
                try:
                    with node.incoming_queue_size_lock:
                        node.incoming_queue_size = max(0, node.incoming_queue_size - int(accounted_size))
                except Exception:
                    node.logger.exception("Failed updating incoming_queue_size")

    node.logger.info("Incoming message processor stopped")


def populate_incoming_messages(node: "Node") -> None:
    """Receive UDP packets and feed the incoming queue."""
    stop = getattr(node, "communication_stop_event", None)
    while stop is None or not stop.is_set():
        try:
            data, addr = node.incoming_socket.recvfrom(4096)
            enqueue_incoming(node, addr, payload=data)
        except socket.timeout:
            continue
        except OSError:
            if stop is not None and stop.is_set():
                break
            node.logger.warning("Error populating incoming queue: socket closed")
        except Exception as exc:
            node.logger.warning("Error populating incoming queue: %s", exc)

    node.logger.info("Incoming message populator stopped")
