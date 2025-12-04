import socket, threading
from queue import Queue
from typing import Tuple, Optional
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .. import Node

from . import Route, Message
from .handlers.handshake import handle_handshake
from .handlers.ping import handle_ping
from .handlers.storage_request import handle_storage_request
from .models.message import MessageTopic
from .util import address_str_to_host_and_port

def load_x25519(hex_key: Optional[str]) -> X25519PrivateKey:
    """DH key for relaying (always X25519)."""
    if hex_key:
        return X25519PrivateKey.from_private_bytes(bytes.fromhex(hex_key))
    return X25519PrivateKey.generate()

def load_ed25519(hex_key: Optional[str]) -> Optional[ed25519.Ed25519PrivateKey]:
    """Signing key for validation (Ed25519), or None if absent."""
    return ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(hex_key)) \
           if hex_key else None

def make_routes(
    relay_pk: X25519PublicKey,
    val_sk: Optional[ed25519.Ed25519PrivateKey]
) -> Tuple[Route, Optional[Route]]:
    """Peer route (DH pubkey) + optional validation route (ed pubkey)."""
    peer_rt = Route(relay_pk)
    val_rt  = Route(val_sk.public_key()) if val_sk else None
    return peer_rt, val_rt

def setup_outgoing(
    use_ipv6: bool
) -> Tuple[socket.socket, Queue, threading.Thread]:
    fam  = socket.AF_INET6 if use_ipv6 else socket.AF_INET
    sock = socket.socket(fam, socket.SOCK_DGRAM)
    q    = Queue()
    thr  = threading.Thread(target=lambda: None, daemon=True)
    thr.start()
    return sock, q, thr

def make_maps():
    """Empty lookup maps: peers and addresses."""
    return


def process_incoming_messages(node: "Node") -> None:
    """Process incoming messages (placeholder)."""
    node_logger = node.logger
    while True:
        try:
            data, addr = node.incoming_queue.get()
        except Exception as exc:
            node_logger.exception("Error taking from incoming queue")
            continue

        try:
            message = Message.from_bytes(data)
        except Exception as exc:
            node_logger.warning("Error decoding message: %s", exc)
            continue

        if message.handshake:
            if handle_handshake(node, addr, message):
                continue

        match message.topic:
            case MessageTopic.PING:
                handle_ping(node, addr, message.content)
            case MessageTopic.OBJECT_REQUEST:
                pass
            case MessageTopic.OBJECT_RESPONSE:
                pass
            case MessageTopic.ROUTE_REQUEST:
                pass
            case MessageTopic.ROUTE_RESPONSE:
                pass
            case MessageTopic.TRANSACTION:
                if node.validation_secret_key is None:
                    continue
                node._validation_transaction_queue.put(message.content)

            case MessageTopic.STORAGE_REQUEST:
                handle_storage_request(node, addr, message)
            
            case _:
                continue


def populate_incoming_messages(node: "Node") -> None:
    """Receive UDP packets and feed the incoming queue (placeholder)."""
    node_logger = node.logger
    while True:
        try:
            data, addr = node.incoming_socket.recvfrom(4096)
            node.incoming_queue.put((data, addr))
        except Exception as exc:
            node_logger.warning("Error populating incoming queue: %s", exc)

def communication_setup(node: "Node", config: dict):
    node.logger.info("Setting up node communication")
    node.use_ipv6              = config.get('use_ipv6', False)

    # key loading
    node.relay_secret_key      = load_x25519(config.get('relay_secret_key'))
    node.validation_secret_key = load_ed25519(config.get('validation_secret_key'))

    # derive pubs + routes
    node.relay_public_key      = node.relay_secret_key.public_key()
    node.validation_public_key = (
        node.validation_secret_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        if node.validation_secret_key
        else None
    )
    node.peer_route, node.validation_route = make_routes(
        node.relay_public_key,
        node.validation_secret_key
    )

    # sockets + queues + threads
    incoming_port = config.get('incoming_port', 7373)
    fam = socket.AF_INET6 if node.use_ipv6 else socket.AF_INET
    node.incoming_socket = socket.socket(fam, socket.SOCK_DGRAM)
    if node.use_ipv6:
        node.incoming_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    node.incoming_socket.bind(("::" if node.use_ipv6 else "0.0.0.0", incoming_port or 0))
    node.incoming_port = node.incoming_socket.getsockname()[1]
    node.logger.info(
        "Incoming UDP socket bound to %s:%s",
        "::" if node.use_ipv6 else "0.0.0.0",
        node.incoming_port,
    )
    node.incoming_queue = Queue()
    node.incoming_populate_thread = threading.Thread(
        target=populate_incoming_messages,
        args=(node,),
        daemon=True,
    )
    node.incoming_process_thread = threading.Thread(
        target=process_incoming_messages,
        args=(node,),
        daemon=True,
    )
    node.incoming_populate_thread.start()
    node.incoming_process_thread.start()

    (node.outgoing_socket,
        node.outgoing_queue,
        node.outgoing_thread
    ) = setup_outgoing(node.use_ipv6)

    # other workers & maps
    node.object_request_queue = Queue()
    node.peer_manager_thread  = threading.Thread(
        target=node._relay_peer_manager,
        daemon=True
    )
    node.peer_manager_thread.start()

    node.peers, node.addresses = {}, {} # peers: Dict[bytes,Peer], addresses: Dict[(str,int),bytes]
    latest_hash = getattr(node, "latest_block_hash", None)
    if not isinstance(latest_hash, (bytes, bytearray)) or len(latest_hash) != 32:
        node.latest_block_hash = bytes(32)
    else:
        node.latest_block_hash = bytes(latest_hash)

    # bootstrap pings
    bootstrap_peers = config.get('bootstrap', [])
    for addr in bootstrap_peers:
        try:
            host, port = address_str_to_host_and_port(addr)  # type: ignore[arg-type]
        except Exception as exc:
            node.logger.warning("Invalid bootstrap address %s: %s", addr, exc)
            continue

        handshake_message = Message(handshake=True, sender=node.relay_public_key)
        
        node.outgoing_queue.put((handshake_message.to_bytes(), (host, port)))
        node.logger.info("Sent bootstrap handshake to %s:%s", host, port)

    node.logger.info(
        "Communication ready (incoming_port=%s, outgoing_socket_initialized=%s, bootstrap_count=%s)",
        node.incoming_port,
        node.outgoing_socket is not None,
        len(bootstrap_peers),
    )
