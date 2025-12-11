import socket, threading
from queue import Queue
from typing import Tuple, Optional
from astreum.communication.handlers.object_request import (
    handle_object_request,
    ObjectRequest,
    ObjectRequestType,
)
from astreum.communication.handlers.object_response import ObjectResponse, ObjectResponseType
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
from .handlers.route_request import handle_route_request
from .handlers.route_response import handle_route_response
from .handlers.storage_request import handle_storage_request
from .models.message import MessageTopic
from .util import address_str_to_host_and_port
from ..utils.bytes import hex_to_bytes
from ..storage.models.atom import Atom

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

def decode_object_provider(payload: bytes) -> Tuple[bytes, str, int]:
    """Decode provider payload (peer pub key + IPv4 + port)."""
    expected_len = 32 + 4 + 2
    if len(payload) < expected_len:
        raise ValueError("provider payload too short")

    provider_public_key = payload[:32]
    provider_ip_bytes = payload[32:36]
    provider_port_bytes = payload[36:38]

    provider_address = socket.inet_ntoa(provider_ip_bytes)
    provider_port = int.from_bytes(provider_port_bytes, byteorder="big", signed=False)
    return provider_public_key, provider_address, provider_port

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
                handle_object_request(node, addr, message)

            case MessageTopic.OBJECT_RESPONSE:
                try:
                    object_response = ObjectResponse.from_bytes(message.body)
                except Exception as e:
                    print(f"Error processing OBJECT_RESPONSE: {e}")
                    continue

                if not node.has_atom_req(object_response.atom_id):
                    continue
                
                match object_response.type:
                    case ObjectResponseType.OBJECT_FOUND:

                        atom = Atom.from_bytes(object_response.data)
                        atom_id = atom.object_id()
                        if object_response.atom_id == atom_id:
                            node.pop_atom_req(atom_id)
                            node._hot_storage_set(atom_id, atom)

                    case ObjectResponseType.OBJECT_PROVIDER:
                        _provider_public_key, provider_address, provider_port = decode_object_provider(object_response.data)
                        obj_req = ObjectRequest(
                            type=ObjectRequestType.OBJECT_GET,
                            data=b"",
                            atom_id=object_response.atom_id,
                        )
                        obj_req_bytes = obj_req.to_bytes()
                        obj_req_msg = Message(
                            topic=MessageTopic.OBJECT_REQUEST,
                            body=obj_req_bytes,
                            sender=node.relay_public_key,
                        )
                        node.outgoing_queue.put((obj_req_msg.to_bytes(), (provider_address, provider_port)))

                    case ObjectResponseType.OBJECT_NEAREST_PEER:
                        pass
            
            case MessageTopic.ROUTE_REQUEST:
                handle_route_request(node, addr, message)
            
            case MessageTopic.ROUTE_RESPONSE:
                handle_route_response(node, addr, message)
            
            case MessageTopic.TRANSACTION:
                if node.validation_secret_key is None:
                    continue
                node._validation_transaction_queue.put(message.content)
            
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
    # track atom requests we initiated; guarded by atom_requests_lock on the node
    node.peer_manager_thread  = threading.Thread(
        target=node._relay_peer_manager,
        daemon=True
    )
    node.peer_manager_thread.start()

    node.peers, node.addresses = {}, {} # peers: Dict[bytes,Peer], addresses: Dict[(str,int),bytes]

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
    node.is_connected = True
