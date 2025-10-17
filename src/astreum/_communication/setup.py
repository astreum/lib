import socket, threading
from datetime import datetime, timezone
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

from . import Route, Message
from .message import MessageTopic
from .peer import Peer
from .ping import Ping
from .util import address_str_to_host_and_port

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
    while True:
        try:
            data, addr = node.incoming_queue.get()
        except Exception as exc:
            print(f"Error taking from incoming queue: {exc}")
            continue

        try:
            message = Message.from_bytes(data)
        except Exception as exc:
            print(f"Error decoding message: {exc}")
            continue

        if message.handshake:
            sender_key = message.sender

            try:
                sender_public_key_bytes = sender_key.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
            except Exception as exc:
                print(f"Error extracting sender key bytes: {exc}")
                continue

            # Normalize remote address (IPv6 tuples may be 4 elements)
            try:
                host, port = addr[0], int(addr[1])
            except Exception:
                continue
            address_key = (host, port)

            old_key_bytes = node.addresses.get(address_key)
            node.addresses[address_key] = sender_public_key_bytes

            if old_key_bytes is None:
                # brand-new address -> brand-new peer
                try:
                    peer = Peer(node.relay_secret_key, sender_key)
                except Exception:
                    continue
                
                node.peers[sender_public_key_bytes] = peer
                node.peer_route.add_peer(sender_public_key_bytes)

                response = Message(handshake=True, sender=node.relay_public_key)
                node.outgoing_queue.put((response.to_bytes(), address_key))
                continue
            
            elif old_key_bytes == sender_public_key_bytes:
                # existing mapping with same key -> nothing to change
                pass
            
            else:
                # address reused with a different key -> replace peer
                node.peers.pop(old_key_bytes, None)
                try:
                    peer = Peer(node.relay_secret_key, sender_key)
                except Exception:
                    continue
                
                node.peers[sender_public_key_bytes] = peer

        match message.topic:
            case MessageTopic.PING:
                try:
                    host, port = addr[0], int(addr[1])
                except Exception:
                    continue
                address_key = (host, port)
                sender_public_key_bytes = node.addresses.get(address_key)
                if sender_public_key_bytes is None:
                    continue
                peer = node.peers.get(sender_public_key_bytes)
                if peer is None:
                    continue
                try:
                    ping = Ping.from_bytes(message.content)
                except Exception as exc:
                    print(f"Error decoding ping: {exc}")
                    continue

                peer.timestamp = datetime.now(timezone.utc)
                peer.latest_block = ping.latest_block

                validation_route = node.validation_route
                if validation_route is None:
                    continue
                if ping.is_validator:
                    try:
                        validation_route.add_peer(sender_public_key_bytes)
                    except Exception:
                        pass
                else:
                    try:
                        validation_route.remove_peer(sender_public_key_bytes)
                    except Exception:
                        pass
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
            
            case _:
                continue


def populate_incoming_messages(node: "Node") -> None:
    """Receive UDP packets and feed the incoming queue (placeholder)."""
    while True:
        try:
            data, addr = node.incoming_socket.recvfrom(4096)
            node.incoming_queue.put((data, addr))
        except Exception as exc:
            print(f"Error populating incoming queue: {exc}")

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
    incoming_port = config.get('incoming_port', 7373)
    fam = socket.AF_INET6 if node.use_ipv6 else socket.AF_INET
    node.incoming_socket = socket.socket(fam, socket.SOCK_DGRAM)
    if node.use_ipv6:
        node.incoming_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    node.incoming_socket.bind(("::" if node.use_ipv6 else "0.0.0.0", incoming_port or 0))
    node.incoming_port = node.incoming_socket.getsockname()[1]
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
    for addr in config.get('bootstrap', []):
        try:
            host, port = address_str_to_host_and_port(addr)  # type: ignore[arg-type]
        except Exception:
            continue

        handshake_message = Message(handshake=True, sender=node.relay_public_key)
        
        node.outgoing_queue.put((handshake_message.to_bytes(), (host, port)))
