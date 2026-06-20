import socket, threading, time
from queue import Queue
from typing import Tuple, Optional, Set
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
from .processors.incoming import (
    process_incoming_messages,
    populate_incoming_messages,
)
from .processors.outgoing import process_outgoing_messages
from .processors.peer import manage_peer
from .outgoing_queue import enqueue_outgoing
from .util import address_str_to_host_and_port
from ..storage.thread import storage_thread
from ..utils.bytes import hex_to_bytes
from ..utils.config import DEFAULT_SEED

def load_x25519(hex_key: Optional[str]) -> X25519PrivateKey:
    """DH key for relaying (always X25519)."""
    if hex_key:
        return X25519PrivateKey.from_private_bytes(bytes.fromhex(hex_key))
    return X25519PrivateKey.generate()

def make_routes(
    relay_pk: X25519PublicKey,
    val_sk: Optional[ed25519.Ed25519PrivateKey]
) -> Tuple[Route, Optional[Route]]:
    """Peer route (DH pubkey) + optional validation route (ed pubkey)."""
    peer_rt = Route(relay_pk)
    val_rt  = Route(val_sk.public_key()) if val_sk else None
    return peer_rt, val_rt

def make_maps():
    """Empty lookup maps: peers and addresses."""
    return


def _resolve_default_seed_ips(node: "Node", default_seed: Optional[str]) -> Set[str]:
    if default_seed is None:
        return set()
    try:
        host, port = address_str_to_host_and_port(default_seed)
    except Exception as exc:
        node.logger.warning("Invalid default seed %s: %s", default_seed, exc)
        return set()
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_DGRAM)
    except Exception as exc:
        node.logger.warning("Failed resolving default seed %s:%s: %s", host, port, exc)
        return set()
    resolved = {info[4][0] for info in infos if info[4]}
    if resolved:
        resolved_list = ", ".join(sorted(resolved))
        node.logger.info("Default seed resolved to %s", resolved_list)
    else:
        node.logger.warning("No IPs resolved for default seed %s:%s", host, port)
    return resolved


def _resolve_relay_ip_address(node: "Node") -> Optional[str]:
    try:
        host, port = address_str_to_host_and_port(DEFAULT_SEED)
    except Exception as exc:
        node.logger.warning("Invalid default seed %s: %s", DEFAULT_SEED, exc)
        return None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((host, port))
            local_ip = sock.getsockname()[0]
            socket.inet_aton(local_ip)
            return local_ip
    except Exception as exc:
        node.logger.debug("Failed deriving relay IP via default seed: %s", exc)
    return None


def communication_setup(node: "Node", config: dict):
    node.logger.info("Setting up node communication")
    node.use_ipv6              = config.get('use_ipv6', False)
    node.peers_lock = threading.RLock()
    node.communication_stop_event = threading.Event()
    default_seed = config.get("default_seed")
    node.default_seed_ips = _resolve_default_seed_ips(node, default_seed)
    node.relay_ip_address = _resolve_relay_ip_address(node)

    # key loading
    node.relay_secret_key      = load_x25519(config.get('relay_secret_key'))

    # derive pubs + routes
    node.relay_public_key      = node.relay_secret_key.public_key()
    node.relay_public_key_bytes = node.relay_public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    node.config["relay_public_key"] = node.relay_public_key
    node.config["relay_public_key_bytes"] = node.relay_public_key_bytes
    node.peer_route, node.validation_route = make_routes(
        node.relay_public_key,
        node.config.get("validation_secret_key")
    )

    # connection state & atom request tracking
    node.is_connected = False
    node.expr_requests = {}
    node.expr_requests_lock = threading.RLock()

    # sockets + queues + threads
    with node.peers_lock:
        node.peers = {}


    incoming_port = config.get("incoming_port")
    if incoming_port is None:
        raise ValueError("incoming_port must be configured before communication setup")
    fam = socket.AF_INET6 if node.use_ipv6 else socket.AF_INET
    node.incoming_socket = socket.socket(fam, socket.SOCK_DGRAM)
    if node.use_ipv6:
        node.incoming_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    node.incoming_socket.bind(("::" if node.use_ipv6 else "0.0.0.0", incoming_port))
    bound_port = node.incoming_socket.getsockname()[1]
    if incoming_port != 0 and bound_port != incoming_port:
        raise OSError(
            f"incoming_port mismatch: requested {incoming_port}, got {bound_port}"
        )
    node.config["incoming_port"] = bound_port if incoming_port == 0 else incoming_port
    node.incoming_socket.settimeout(0.5)
    node.logger.info(
        "Incoming UDP socket bound to %s:%s",
        "::" if node.use_ipv6 else "0.0.0.0",
        node.config["incoming_port"],
    )
    node.incoming_queue = Queue()
    node.incoming_queue_size = 0
    node.incoming_queue_size_lock = threading.RLock()
    node.incoming_queue_size_limit = node.config.get("incoming_queue_size_limit", 0)
    node.incoming_queue_timeout = node.config.get("incoming_queue_timeout", 0)
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

    node.outgoing_queue = Queue()

    node.outgoing_thread = threading.Thread(
        target=process_outgoing_messages,
        args=(node,),
        daemon=True,
    )
    node.outgoing_thread.start()

    node.peer_manager_thread  = threading.Thread(
        target=manage_peer,
        args=(node,),
        daemon=True
    )
    node.peer_manager_thread.start()

    latest_block_hex = config.get("latest_block_hash")
    if latest_block_hex:
        try:
            node.latest_block_hash = hex_to_bytes(latest_block_hex, expected_length=32)
        except Exception as exc:
            node.logger.warning("Invalid latest_block_hash in config: %s", exc)
            node.latest_block_hash = None
    # else: preserve the existing instance attribute — don't wipe it.
    # communication_setup runs on every node.connect() and should only
    # overwrite latest_block_hash when config explicitly provides one.

    node.logger.info(
        "Communication ready (incoming_port=%s, bootstrap_count=%s)",
        node.config["incoming_port"],
        len(node.bootstrap_peers),
    )
    node.is_connected = True

    # bootstrap pings (requires connected state for enqueue_outgoing)
    for addr in node.bootstrap_peers:
        try:
            host, port = address_str_to_host_and_port(addr)  # type: ignore[arg-type]
        except Exception as exc:
            node.logger.warning("Invalid bootstrap address %s: %s", addr, exc)
            continue

        handshake_message = Message(
            handshake=True,
            sender=node.relay_public_key,
            incoming_port=node.config["incoming_port"],
            content=b"",
        )
        enqueue_outgoing(
            node,
            (host, port),
            message=handshake_message,
            difficulty=1,
        )
        node.logger.info("Sent bootstrap handshake to %s:%s", host, port)
    if node.bootstrap_peers:
        node._bootstrap_last_attempt = time.time()

    try:
        node.storage_request_current_price = max(
            0,
            int(node.config.get("storage_request_minimum_price", 0) or 0),
        )
    except Exception:
        node.storage_request_current_price = 0
    
    node.storage_thread = threading.Thread(
        target=storage_thread,
        args=(node,),
        daemon=True,
    )
    node.storage_thread.start()
