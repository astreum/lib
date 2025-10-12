import socket, threading
from queue import Queue
from typing import Tuple, Optional
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .. import Node

from .import Route

def load_x25519(hex_key: Optional[str]) -> X25519PrivateKey:
    """DH key for relaying (always X25519)."""
    return 

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

def setup_udp(
    bind_port: int,
    use_ipv6: bool
) -> Tuple[socket.socket, int, Queue, threading.Thread, threading.Thread]:
    fam  = socket.AF_INET6 if use_ipv6 else socket.AF_INET
    sock = socket.socket(fam, socket.SOCK_DGRAM)
    if use_ipv6:
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    sock.bind(("::" if use_ipv6 else "0.0.0.0", bind_port or 0))
    port = sock.getsockname()[1]

    q    = Queue()
    pop  = threading.Thread(target=lambda: None, daemon=True)
    proc = threading.Thread(target=lambda: None, daemon=True)
    pop.start(); proc.start()
    return sock, port, q, pop, proc

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

def communication_setup(node: "Node", config: dict):
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
    (node.incoming_socket,
        node.incoming_port,
        node.incoming_queue,
        node.incoming_populate_thread,
        node.incoming_process_thread
    ) = setup_udp(config.get('incoming_port', 7373), node.use_ipv6)

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

    node.peers, node.addresses = {}, {} # peers: Dict[X25519PublicKey,Peer], addresses: Dict[(str,int),X25519PublicKey]

    # bootstrap pings
    for addr in config.get('bootstrap', []):
        node._send_ping(addr)
