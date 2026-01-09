import heapq, os, socket, threading, time
from pathlib import Path
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
from ..utils.bytes import hex_to_bytes

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


def advertise_cold_storage(node: "Node") -> None:
    """Advertise all cold storage atom ids to the closest known peer."""
    node_logger = node.logger
    cold_path = node.config.get("cold_storage_path")
    if not cold_path:
        node_logger.debug("Cold storage disabled; skipping cold atom advertisement")
        return
    advertise_limit = node.config.get("cold_storage_advertise_limit", 1000)
    if advertise_limit == 0:
        node_logger.debug(
            "Cold storage advertisement disabled; skipping cold atom advertisement"
        )
        return

    directory = Path(cold_path)
    if not directory.exists():
        node_logger.warning("Cold storage path %s missing; cannot advertise atoms", directory)
        return
    if not directory.is_dir():
        node_logger.warning("Cold storage path %s is not a directory; skipping", directory)
        return

    advertised = 0
    skipped = 0
    if advertise_limit < 0:
        for file_path in directory.glob("*.bin"):
            if not file_path.is_file():
                skipped += 1
                continue
            atom_hex = file_path.stem
            if len(atom_hex) != 64:
                skipped += 1
                continue
            try:
                atom_id = bytes.fromhex(atom_hex)
            except ValueError:
                skipped += 1
                continue
            if len(atom_id) != 32:
                skipped += 1
                continue
            node._network_set(atom_id)
            advertised += 1
    else:
        heap = []
        for entry in os.scandir(directory):
            name = entry.name
            if not name.endswith(".bin"):
                continue
            if not entry.is_file():
                skipped += 1
                continue
            atom_hex = name[:-4]
            if len(atom_hex) != 64:
                skipped += 1
                continue
            try:
                atom_id = bytes.fromhex(atom_hex)
            except ValueError:
                skipped += 1
                continue
            if len(atom_id) != 32:
                skipped += 1
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                skipped += 1
                continue
            if len(heap) < advertise_limit:
                heapq.heappush(heap, (mtime, atom_id))
            else:
                if mtime > heap[0][0]:
                    heapq.heapreplace(heap, (mtime, atom_id))
        for _, atom_id in sorted(heap, key=lambda item: item[0], reverse=True):
            node._network_set(atom_id)
            advertised += 1

    node_logger.info(
        "Cold storage advertisement complete (advertised=%s, skipped=%s)",
        advertised,
        skipped,
    )


def manage_storage_index(node: "Node") -> None:
    interval = node.config.get("storage_index_interval", 0)
    if not interval:
        node.logger.info("Storage index advertiser disabled")
        return
    node.logger.info("Storage index advertiser started (interval=%ss)", interval)
    stop = getattr(node, "communication_stop_event", None)
    while stop is None or not stop.is_set():
        if stop is not None and stop.wait(interval):
            break
        try:
            advertise_cold_storage(node)
        except Exception:
            node.logger.exception("Storage index advertisement failed")
    node.logger.info("Storage index advertiser stopped")


def communication_setup(node: "Node", config: dict):
    node.logger.info("Setting up node communication")
    node.use_ipv6              = config.get('use_ipv6', False)
    node.peers_lock = threading.RLock()
    node.communication_stop_event = threading.Event()
    default_seed = config.get("default_seed")
    node.default_seed_ips = _resolve_default_seed_ips(node, default_seed)

    # key loading
    node.relay_secret_key      = load_x25519(config.get('relay_secret_key'))
    node.validation_secret_key = load_ed25519(config.get('validation_secret_key'))

    # derive pubs + routes
    node.relay_public_key      = node.relay_secret_key.public_key()
    node.relay_public_key_bytes = node.relay_public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
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

    # connection state & atom request tracking
    node.is_connected = False
    node.atom_requests = set()
    node.atom_requests_lock = threading.RLock()

    # sockets + queues + threads
    incoming_port = config.get('incoming_port')
    fam = socket.AF_INET6 if node.use_ipv6 else socket.AF_INET
    node.incoming_socket = socket.socket(fam, socket.SOCK_DGRAM)
    if node.use_ipv6:
        node.incoming_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    node.incoming_socket.bind(("::" if node.use_ipv6 else "0.0.0.0", incoming_port or 0))
    node.incoming_port = node.incoming_socket.getsockname()[1]
    node.incoming_socket.settimeout(0.5)
    node.logger.info(
        "Incoming UDP socket bound to %s:%s",
        "::" if node.use_ipv6 else "0.0.0.0",
        node.incoming_port,
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

    node.outgoing_socket = socket.socket(
        socket.AF_INET6 if node.use_ipv6 else socket.AF_INET,
        socket.SOCK_DGRAM,
    )
    node.outgoing_socket.settimeout(0.5)
    node.outgoing_queue = Queue()
    node.outgoing_queue_size = 0
    node.outgoing_queue_size_lock = threading.RLock()
    node.outgoing_queue_size_limit = node.config.get("outgoing_queue_size_limit", 0)
    node.outgoing_queue_timeout = node.config.get("outgoing_queue_timeout", 0)

    node.outgoing_thread = threading.Thread(
        target=process_outgoing_messages,
        args=(node,),
        daemon=True,
    )
    node.outgoing_thread.start()

    # other workers & maps
    # track atom requests we initiated; guarded by atom_requests_lock on the node
    node.peer_manager_thread  = threading.Thread(
        target=manage_peer,
        args=(node,),
        daemon=True
    )
    node.peer_manager_thread.start()

    with node.peers_lock:
        node.peers = {} # Dict[bytes,Peer]

    latest_block_hex = config.get("latest_block_hash")
    if latest_block_hex:
        try:
            node.latest_block_hash = hex_to_bytes(latest_block_hex, expected_length=32)
        except Exception as exc:
            node.logger.warning("Invalid latest_block_hash in config: %s", exc)
            node.latest_block_hash = None
    else:
        node.latest_block_hash = None

    # bootstrap pings
    bootstrap_peers = node.bootstrap_peers
    for addr in bootstrap_peers:
        try:
            host, port = address_str_to_host_and_port(addr)  # type: ignore[arg-type]
        except Exception as exc:
            node.logger.warning("Invalid bootstrap address %s: %s", addr, exc)
            continue

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
    node.logger.info("Sent bootstrap handshake to %s:%s", host, port)
    if bootstrap_peers:
        node._bootstrap_last_attempt = time.time()

    node.logger.info(
        "Communication ready (incoming_port=%s, outgoing_socket_initialized=%s, bootstrap_count=%s)",
        node.incoming_port,
        node.outgoing_socket is not None,
        len(bootstrap_peers),
    )
    node.is_connected = True
    advertise_cold_storage(node)
    node.storage_index_thread = threading.Thread(
        target=manage_storage_index,
        args=(node,),
        daemon=True,
    )
    node.storage_index_thread.start()
