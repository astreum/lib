import socket
import threading
import time
from queue import Queue
from pathlib import Path
from typing import Tuple, Dict, Union, Optional, List
from datetime import datetime, timedelta, timezone
import uuid
from .format import encode, decode
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives import serialization
from .crypto import ed25519, x25519
from enum import IntEnum
import blake3
import struct

class ObjectRequestType(IntEnum):
    OBJECT_GET = 0
    OBJECT_PUT = 1

class ObjectRequest:
    type: ObjectRequestType
    data: bytes
    hash: bytes

    def __init__(self, type: ObjectRequestType, data: bytes, hash: bytes = None):
        self.type = type
        self.data = data
        self.hash = hash

    def to_bytes(self):
        return encode([self.type.value, self.data, self.hash])

    @classmethod
    def from_bytes(cls, data: bytes):
        type_val, data_val, hash_val = decode(data)
        return cls(type=ObjectRequestType(type_val[0]), data=data_val, hash=hash_val)

class ObjectResponseType(IntEnum):
    OBJECT_FOUND = 0
    OBJECT_PROVIDER = 1
    OBJECT_NEAREST_PEER = 2

class ObjectResponse:
    type: ObjectResponseType
    data: bytes
    hash: bytes

    def __init__(self, type: ObjectResponseType, data: bytes, hash: bytes = None):
        self.type = type
        self.data = data
        self.hash = hash

    def to_bytes(self):
        return encode([self.type.value, self.data, self.hash])

    @classmethod
    def from_bytes(cls, data: bytes):
        type_val, data_val, hash_val = decode(data)
        return cls(type=ObjectResponseType(type_val[0]), data=data_val, hash=hash_val)

class MessageTopic(IntEnum):
    PING = 0
    OBJECT_REQUEST = 1
    OBJECT_RESPONSE = 2
    ROUTE_REQUEST = 3
    ROUTE_RESPONSE = 4

class Message:
    body: bytes
    topic: MessageTopic
    
    def to_bytes(self):
        return encode([self.body, [self.topic.value]])

    @classmethod
    def from_bytes(cls, data: bytes):
        body, topic = decode(data)
        return cls(body=body, topic=MessageTopic(topic[0]))

class Envelope:
    encrypted: bool
    message: Message
    nonce: int
    sender: X25519PublicKey
    timestamp: datetime

    def __init__(self, message: Message, sender: X25519PublicKey, encrypted: bool = False, nonce: int = 0, timestamp: Union[int, datetime, None] = None, difficulty: int = 1):
        self.encrypted = encrypted
        encrypted_bytes = b'\x01' if self.encrypted else b'\x00'

        self.message = message
        message_bytes = message.to_bytes()

        self.sender = sender
        self.sender_bytes = sender.public_bytes()

        self.nonce = nonce
    
        if timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
            timestamp_int = int(self.timestamp.timestamp())
        elif isinstance(timestamp, int):
            self.timestamp = datetime.fromtimestamp(timestamp, timezone.utc)
            timestamp_int = timestamp
        elif isinstance(timestamp, datetime):
            self.timestamp = timestamp
            timestamp_int = int(timestamp.timestamp())
        else:
            raise TypeError("Timestamp must be an int (Unix timestamp), datetime object, or None")

        def count_leading_zero_bits(data: bytes) -> int:
            count = 0
            for b in data:
                if b == 0:
                    count += 8
                else:
                    count += 8 - b.bit_length()
                    break
            return count

        while True:
            envelope_bytes = encode([
                encrypted_bytes,
                message_bytes,
                self.nonce,
                self.sender_bytes,
                timestamp_int
            ])
            envelope_hash = blake3.blake3(envelope_bytes).digest()
            if count_leading_zero_bits(envelope_hash) >= difficulty:
                self.hash = envelope_hash
                break
            self.nonce += 1

    def to_bytes(self):
        encrypted_bytes = b'\x01' if self.encrypted else b'\x00'
        
        return encode([
            encrypted_bytes,
            self.message.to_bytes(),
            self.nonce,
            self.sender.public_bytes(),
            int(self.timestamp.timestamp())
        ])

    @classmethod
    def from_bytes(cls, data: bytes):
        encrypted_bytes, message_bytes, nonce, sender_bytes, timestamp_int = decode(data)
        return cls(
            encrypted=(encrypted_bytes == b'\x01'),
            message=Message.from_bytes(message_bytes),
            nonce=nonce,
            sender=X25519PublicKey.from_public_bytes(sender_bytes),
            timestamp=datetime.fromtimestamp(timestamp_int, timezone.utc)
        )

class Peer:
    def __init__(self, node_secret_key: X25519PrivateKey, peer_public_key: X25519PublicKey, address: Tuple[str, int]):
        self.shared_key = x25519.generate_shared_key(node_secret_key, peer_public_key)
        self.address = address
        self.timestamp = datetime.now(timezone.utc)

class Route:
    def __init__(self, relay_public_key: X25519PublicKey, bucket_size: int = 16):
        self.relay_public_key_bytes = relay_public_key.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
        self.bucket_size = bucket_size
        self.buckets: Dict[int, List[X25519PublicKey]] = {
            i: [] for i in range(len(self.relay_public_key_bytes) * 8)
        }
        self.peers = {}

    @staticmethod
    def _matching_leading_bits(a: bytes, b: bytes) -> int:
        for byte_index, (ba, bb) in enumerate(zip(a, b)):
            diff = ba ^ bb
            if diff:
                return byte_index * 8 + (8 - diff.bit_length())
        return len(a) * 8

    def add_peer(self, peer_public_key: X25519PublicKey):
        peer_public_key_bytes = peer_public_key.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
        bucket_idx = self._matching_leading_bits(self.relay_public_key_bytes, peer_public_key_bytes)
        if len(self.buckets[bucket_idx]) < self.bucket_size:
            self.buckets[bucket_idx].append(peer_public_key)  


def encode_ip_address(host: str, port: int) -> bytes:
    ip_bytes = socket.inet_pton(socket.AF_INET6 if ':' in host else socket.AF_INET, host)
    port_bytes = struct.pack("!H", port)
    return ip_bytes + port_bytes

def decode_ip_address(data: bytes) -> tuple[str, int]:
    if len(data) == 6:
        ip = socket.inet_ntop(socket.AF_INET, data[:4])
        port = struct.unpack("!H", data[4:6])[0]
    elif len(data) == 18:
        ip = socket.inet_ntop(socket.AF_INET6, data[:16])
        port = struct.unpack("!H", data[16:18])[0]
    else:
        raise ValueError("Invalid address byte format")
    return ip, port

# =========
# MACHINE
# =========

class Expr:
    class ListExpr:
        def __init__(self, elements: List['Expr']):
            self.elements = elements

        def __eq__(self, other):
            if not isinstance(other, Expr.ListExpr):
                return NotImplemented
            return self.elements == other.elements

        def __ne__(self, other):
            return not self.__eq__(other)

        @property
        def value(self):
            inner = " ".join(str(e) for e in self.elements)
            return f"({inner})"


        def __repr__(self):
            if not self.elements:
                return "()"
            
            inner = " ".join(str(e) for e in self.elements)
            return f"({inner})"
        
        def __iter__(self):
            return iter(self.elements)
        
        def __getitem__(self, index: Union[int, slice]):
            return self.elements[index]

        def __len__(self):
            return len(self.elements)

    class Symbol:
        def __init__(self, value: str):
            self.value = value

        def __repr__(self):
            return self.value

    class Integer:
        def __init__(self, value: int):
            self.value = value

        def __repr__(self):
            return str(self.value)

    class String:
        def __init__(self, value: str):
            self.value = value

        def __repr__(self):
            return f'"{self.value}"'
        
    class Boolean:
        def __init__(self, value: bool):
            self.value = value

        def __repr__(self):
            return "true" if self.value else "false"

    class Function:
        def __init__(self, params: List[str], body: 'Expr'):
            self.params = params
            self.body = body

        def __repr__(self):
            params_str = " ".join(self.params)
            body_str = str(self.body)
            return f"(fn ({params_str}) {body_str})"

    class Error:
        def __init__(self, message: str, origin: Optional['Expr'] = None):
            self.message = message
            self.origin  = origin

        def __repr__(self):
            if self.origin is None:
                return f'(error "{self.message}")'
            return f'(error "{self.message}" in {self.origin})'

class Env:
    def __init__(
        self,
        data: Optional[Dict[str, Expr]] = None,
        parent_id: Optional[uuid.UUID] = None,
        max_exprs: Optional[int] = 8,
    ):
        self.data: Dict[str, Expr] = data if data is not None else {}
        self.parent_id: Optional[uuid.UUID] = parent_id
        self.max_exprs: Optional[int] = max_exprs

    def put(self, name: str, value: Expr) -> None:
        if (
            self.max_exprs is not None
            and name not in self.data
            and len(self.data) >= self.max_exprs
        ):
            raise RuntimeError(
                f"environment full: {len(self.data)} ≥ max_exprs={self.max_exprs}"
            )
        self.data[name] = value

    def get(self, name: str) -> Optional[Expr]:
        return self.data.get(name)

    def pop(self, name: str) -> Optional[Expr]:
        return self.data.pop(name, None)

    def __repr__(self) -> str:
        return (
            f"Env(size={len(self.data)}, "
            f"max_exprs={self.max_exprs}, "
            f"parent_id={self.parent_id})"
        )


class Transaction:
    def __init__(
        self,
        sender_pk: bytes,
        recipient_pk: bytes,
        amount: int,
        fee: int,
        nonce: int,
        signature: bytes | None = None,
    ) -> None:
        self.sender_pk = sender_pk
        self.recipient_pk = recipient_pk
        self.amount = amount
        self.fee = fee
        self.nonce = nonce
        self.signature = signature

        if self.amount < 0 or self.fee < 0:
            raise ValueError("amount and fee must be non-negative")
        
        if self.fee % 2 != 0:
            raise ValueError("fee must be divisible by two")

        self.tx_body_hash: bytes = blake3.blake3(self._body_bytes()).digest()
        
        if self.signature is not None:
            self.tx_hash = blake3.blake3(self.tx_body_hash + self.signature).digest()
        else:
            self.tx_hash = None

    def sign(self, priv_key: ed25519.Ed25519PrivateKey) -> None:
        if self.signature is not None:
            raise ValueError("transaction already signed")
        sig = priv_key.sign(self.tx_body_hash)
        self.signature = sig
        self.tx_hash = blake3.blake3(self.tx_body_hash + sig).digest()

    def verify_signature(self) -> bool:
        if self.signature is None:
            return False
        try:
            pub = ed25519.Ed25519PublicKey.from_public_bytes(self.sender_pk)
            pub.verify(self.signature, self.tx_body_hash)
            return True
        except Exception:
            return False

    def to_bytes(self) -> bytes:
        sig = self.signature or b""
        return encode([
            self.sender_pk,
            self.recipient_pk,
            self.amount,
            self.fee,
            self.nonce,
            sig,
        ])

    @classmethod
    def from_bytes(cls, blob: bytes) -> 'Transaction':
        sender, recipient, amount, fee, nonce, sig = decode(blob)
        return cls(sender, recipient, int(amount), int(fee), int(nonce), sig)

    def _body_bytes(self) -> bytes:
        return encode([
            self.sender_pk,
            self.recipient_pk,
            self.amount,
            self.fee,
            self.nonce,
        ])

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Transaction):
            return NotImplemented
        return self.tx_hash == other.tx_hash

    def __hash__(self) -> int:
        return int.from_bytes(self.tx_hash, 'big')

class Block:
    def __init__(
        self,
        *,
        number: int,
        prev_block_hash: bytes,
        timestamp: int,
        accounts_hash: bytes,
        total_astre_burned: int,
        tx_limit: int,
        tx_root: bytes,
        vdf_difficulty: int,
        vdf_output: bytes,
        vdf_proof: bytes,
        validator_pk: bytes,
        signature: bytes,
    ) -> None:
        self.accounts_hash = accounts_hash
        self.number = int(number)
        self.prev_block_hash = prev_block_hash
        self.timestamp = int(timestamp)
        self.total_astre_burned = int(total_astre_burned)
        self.tx_limit = int(tx_limit)
        self.tx_root = tx_root
        self.validator_pk = validator_pk
        self.vdf_difficulty = int(vdf_difficulty)
        self.vdf_output = vdf_output
        self.vdf_proof = vdf_proof
        self.signature = signature
        self.body_hash = self._compute_body_hash()

    def _body_fields_without_sig(self) -> list:
        return [
            self.accounts_hash,
            self.number,
            self.prev_block_hash,
            self.timestamp,
            self.total_astre_burned,
            self.tx_limit,
            self.tx_root,
            self.validator_pk,
            self.vdf_difficulty,
            self.vdf_output,
            self.vdf_proof,
        ]

    def _compute_body_hash(self) -> bytes:
        return blake3.blake3(encode(self._body_fields_without_sig())).digest()
    
    def to_bytes(self) -> bytes:
        return encode(self._body_fields_without_sig() + [self.signature])

    @classmethod
    def from_bytes(cls, blob: bytes) -> "Block":
        (
            accounts_hash,
            number,
            prev_block_hash,
            timestamp,
            total_astre_burned,
            tx_limit,
            tx_root,
            validator_pk,
            vdf_difficulty,
            vdf_output,
            vdf_proof,
            signature
        ) = decode(blob)
        return cls(
            number=int(number),
            prev_block_hash=prev_block_hash,
            timestamp=int(timestamp),
            accounts_hash=accounts_hash,
            total_astre_burned=int(total_astre_burned),
            tx_limit=int(tx_limit),
            tx_root=tx_root,
            vdf_difficulty=int(vdf_difficulty),
            vdf_output=vdf_output,
            vdf_proof=vdf_proof,
            validator_pk=validator_pk,
            signature=signature,
        )

    @property
    def hash(self) -> bytes:
        return blake3.blake3(self.body_hash + self.signature).digest()

    def verify_block_signature(self) -> bool:
        try:
            pub = ed25519.Ed25519PublicKey.from_public_bytes(self.validator_pk)
            pub.verify(self.signature, self.body_hash)
            return True
        except Exception:
            return False
  
class Node:
    def __init__(self, config: dict = {}):
        self._machine_setup()
        machine_only = bool(config.get('machine-only', True))
        if not machine_only:
            self._storage_setup(config=config)
            self._relay_setup(config=config)
            self._validation_setup(config=config)

    def _validation_setup(self, config: dict):
        if True:
            self.validator_transactions: Dict[bytes, Transaction] = {}
            # validator thread
        pass

    def _create_block(self):
        pass

    # STORAGE METHODS
    def _storage_setup(self, config: dict):
        storage_path_str = config.get('storage_path')
        if storage_path_str is None:
            self.storage_path = None
            self.memory_storage = {}
        else:
            self.storage_path = Path(storage_path_str)
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self.memory_storage = None

        self.storage_get_relay_timeout = config.get('storage_get_relay_timeout', 5)
        # STORAGE INDEX: (object_hash, encoded (provider_public_key, provider_address))
        self.storage_index = Dict[bytes, bytes]

    def _relay_setup(self, config: dict):
        self.use_ipv6 = config.get('use_ipv6', False)
        incoming_port = config.get('incoming_port', 7373)

        if 'relay_secret_key' in config:
            try:
                private_key_bytes = bytes.fromhex(config['relay_secret_key'])
                self.relay_secret_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
            except Exception as e:
                raise Exception(f"Error loading relay secret key provided: {e}")
        else:
            self.relay_secret_key = ed25519.Ed25519PrivateKey.generate()
        
        self.relay_public_key = self.relay_secret_key.public_key()

        if 'validation_secret_key' in config:
            try:
                private_key_bytes = bytes.fromhex(config['validation_secret_key'])
                self.validation_secret_key = x25519.X25519PrivateKey.from_private_bytes(private_key_bytes)
            except Exception as e:
                raise Exception(f"Error loading validation secret key provided: {e}")

        # setup peer route and validation route
        self.peer_route = Route(self.relay_public_key)
        if self.validation_secret_key:
            self.validation_route = Route(self.relay_public_key)

        # Choose address family based on IPv4 or IPv6
        family = socket.AF_INET6 if self.use_ipv6 else socket.AF_INET

        self.incoming_socket = socket.socket(family, socket.SOCK_DGRAM)
        if self.use_ipv6:
            self.incoming_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        bind_address = "::" if self.use_ipv6 else "0.0.0.0"
        self.incoming_socket.bind((bind_address, incoming_port or 0))
        self.incoming_port = self.incoming_socket.getsockname()[1]
        self.incoming_queue = Queue()

        self.incoming_populate_thread = threading.Thread(target=self._relay_incoming_queue_populating)
        self.incoming_populate_thread.daemon = True
        self.incoming_populate_thread.start()

        self.incoming_process_thread = threading.Thread(target=self._relay_incoming_queue_processing)
        self.incoming_process_thread.daemon = True
        self.incoming_process_thread.start()

        # outgoing thread
        self.outgoing_socket = socket.socket(family, socket.SOCK_DGRAM)
        self.outgoing_queue = Queue()
        self.outgoing_thread = threading.Thread(target=self._relay_outgoing_queue_processor)
        self.outgoing_thread.daemon = True
        self.outgoing_thread.start()

        self.object_request_queue = Queue()

        self.peer_manager_thread = threading.Thread(target=self._relay_peer_manager)
        self.peer_manager_thread.daemon = True
        self.peer_manager_thread.start()

        self.peers = Dict[X25519PublicKey, Peer]

        if 'bootstrap' in config:
            for addr in config['bootstrap']:
                self._send_ping(addr)


    def _local_object_get(self, data_hash: bytes) -> Optional[bytes]:
        if self.memory_storage is not None:
            return self.memory_storage.get(data_hash)

        file_path = self.storage_path / data_hash.hex()
        if file_path.exists():
            return file_path.read_bytes()
        return None

    def _local_object_put(self, hash: bytes, data: bytes) -> bool:
        if self.memory_storage is not None:
            self.memory_storage[hash] = data
            return True

        file_path = self.storage_path / hash.hex()
        file_path.write_bytes(data)
        return True

    def _object_get(self, hash: bytes) -> Optional[bytes]:
        local_data = self._local_object_get(hash)
        if local_data:
            return local_data

        # find the nearest peer route node to the hash and send an object request
        closest_peer = self._get_closest_local_peer(hash)
        if closest_peer:
            object_request_message = Message(topic=MessageTopic.OBJECT_REQUEST, body=hash)
            object_request_envelope = Envelope(message=object_request_message, sender=self.relay_public_key)
            self.outgoing_queue.put((object_request_envelope.to_bytes(), self.peers[closest_peer].address))

        # wait for upto self.storage_get_relay_timeout seconds for the object to be stored/until local_object_get returns something
        start_time = time.time()
        while time.time() - start_time < self.storage_get_relay_timeout:
            # Check if the object has been stored locally
            local_data = self._local_object_get(hash)
            if local_data:
                return local_data
            # Sleep briefly to avoid hammering the local storage
            time.sleep(0.1)
            
        # If we reach here, the object was not received within the timeout period
        return None

    # RELAY METHODS
    def _relay_incoming_queue_populating(self):
        while True:
            try:
                data, addr = self.incoming_socket.recvfrom(4096) 
                self.incoming_queue.put((data, addr))
            except Exception as e:
                print(f"Error in _relay_populate_incoming_queue: {e}")

    def _relay_incoming_queue_processing(self):
        while True:
            try:
                data, addr = self.incoming_queue.get()
                envelope = Envelope.from_bytes(data)
                match envelope.message.topic:
                    case MessageTopic.PING:
                        if envelope.sender in self.peers:
                            self.peers[envelope.sender].timestamp = datetime.now(timezone.utc)
                            continue

                        is_validator_flag = decode(envelope.message.body)

                        if envelope.sender not in self.peers:
                            self._send_ping(addr)

                        peer = Peer(self.relay_secret_key, envelope.sender, addr)
                        self.peers[peer.sender] = peer
                        self.peer_route.add_peer(envelope.sender)
                        if is_validator_flag == [1]:
                            self.validation_route.add_peer(envelope.sender)

                        if peer.timestamp < datetime.now(timezone.utc) - timedelta(minutes=5.0):
                            self._send_ping(addr)
                    
                    case MessageTopic.OBJECT_REQUEST:
                        try:
                            object_request = ObjectRequest.from_bytes(envelope.message.body)

                            match object_request.type:
                                # --------------  OBJECT_GET  --------------
                                case ObjectRequestType.OBJECT_GET:
                                    object_hash = object_request.hash

                                    # 1. If we already have the object, return it.
                                    local_data = self._local_object_get(object_hash)
                                    if local_data is not None:
                                        resp = ObjectResponse(
                                            type=ObjectResponseType.OBJECT_FOUND,
                                            data=local_data,
                                            hash=object_hash
                                        )
                                        msg  = Message(topic=MessageTopic.OBJECT_RESPONSE, body=resp.to_bytes())
                                        env  = Envelope(message=msg, sender=self.relay_public_key)
                                        self.outgoing_queue.put((env.to_bytes(), addr))
                                        return  # done

                                    # 2. If we know a provider, tell the requester.
                                    if not hasattr(self, "storage_index") or not isinstance(self.storage_index, dict):
                                        self.storage_index = {}
                                    if object_hash in self.storage_index:
                                        provider_bytes = self.storage_index[object_hash]
                                        resp = ObjectResponse(
                                            type=ObjectResponseType.OBJECT_PROVIDER,
                                            data=provider_bytes,
                                            hash=object_hash
                                        )
                                        msg = Message(topic=MessageTopic.OBJECT_RESPONSE, body=resp.to_bytes())
                                        env = Envelope(message=msg, sender=self.relay_public_key)
                                        self.outgoing_queue.put((env.to_bytes(), addr))
                                        return  # done

                                    # 3. Otherwise, direct the requester to a peer nearer to the hash.
                                    nearest = self._get_closest_local_peer(object_hash)
                                    if nearest:
                                        nearest_key, nearest_peer = nearest
                                        peer_info = encode([
                                            nearest_key.public_bytes(
                                                encoding=serialization.Encoding.Raw,
                                                format=serialization.PublicFormat.Raw
                                            ),
                                            encode_ip_address(*nearest_peer.address)
                                        ])
                                        resp = ObjectResponse(
                                            type=ObjectResponseType.OBJECT_NEAREST_PEER,
                                            data=peer_info,
                                            hash=object_hash
                                        )
                                        msg = Message(topic=MessageTopic.OBJECT_RESPONSE, body=resp.to_bytes())
                                        env = Envelope(message=msg, sender=self.relay_public_key)
                                        self.outgoing_queue.put((env.to_bytes(), addr))

                                # --------------  OBJECT_PUT  --------------
                                case ObjectRequestType.OBJECT_PUT:
                                    # Ensure the hash is present / correct.
                                    obj_hash = object_request.hash or blake30.blake3(object_request.data).digest()

                                    nearest = self._get_closest_local_peer(obj_hash)
                                    # If a strictly nearer peer exists, forward the PUT.
                                    if nearest and self._is_closer_than_local_peers(obj_hash, nearest[0]):
                                        fwd_req = ObjectRequest(
                                            type=ObjectRequestType.OBJECT_PUT,
                                            data=object_request.data,
                                            hash=obj_hash
                                        )
                                        fwd_msg = Message(topic=MessageTopic.OBJECT_REQUEST, body=fwd_req.to_bytes())
                                        fwd_env = Envelope(message=fwd_msg, sender=self.relay_public_key)
                                        self.outgoing_queue.put((fwd_env.to_bytes(), nearest[1].address))
                                    else:
                                        # We are closest → remember who can provide the object.
                                        provider_record = encode([
                                            envelope.sender.public_bytes(),
                                            encode_ip_address(*addr)
                                        ])
                                        if not hasattr(self, "storage_index") or not isinstance(self.storage_index, dict):
                                            self.storage_index = {}
                                        self.storage_index[obj_hash] = provider_record

                        except Exception as e:
                            print(f"Error processing OBJECT_REQUEST: {e}")

                    case MessageTopic.OBJECT_RESPONSE:
                        try:
                            object_response = ObjectResponse.from_bytes(envelope.message.body)
                            if object_response.hash not in self.object_request_queue:
                                continue
                            
                            match object_response.type:
                                case ObjectResponseType.OBJECT_FOUND:
                                    if object_response.hash != blake30.blake3(object_response.data).digest():
                                        continue
                                    self.object_request_queue.remove(object_response.hash)
                                    self._local_object_put(object_response.hash, object_response.data)

                                case ObjectResponseType.OBJECT_PROVIDER:
                                    _provider_public_key, provider_address = decode(object_response.data)
                                    provider_ip, provider_port = decode_ip_address(provider_address)
                                    object_request_message = Message(topic=MessageTopic.OBJECT_REQUEST, body=object_hash)
                                    object_request_envelope = Envelope(message=object_request_message, sender=self.relay_public_key)
                                    self.outgoing_queue.put((object_request_envelope.to_bytes(), (provider_ip, provider_port)))

                                case ObjectResponseType.OBJECT_NEAREST_PEER:
                                    # -- decode the peer info sent back
                                    nearest_peer_public_key_bytes, nearest_peer_address = (
                                        decode(object_response.data)
                                    )
                                    nearest_peer_public_key = X25519PublicKey.from_public_bytes(
                                        nearest_peer_public_key_bytes
                                    )

                                    # -- XOR-distance between the object hash and the candidate peer
                                    peer_bytes = nearest_peer_public_key.public_bytes(
                                        encoding=serialization.Encoding.Raw,
                                        format=serialization.PublicFormat.Raw,
                                    )
                                    object_response_xor = sum(
                                        a ^ b for a, b in zip(object_response.hash, peer_bytes)
                                    )

                                    # -- forward only if that peer is strictly nearer than any local peer
                                    if self._is_closer_than_local_peers(
                                        object_response.hash, nearest_peer_public_key
                                    ):
                                        nearest_peer_ip, nearest_peer_port = decode_ip_address(
                                            nearest_peer_address
                                        )
                                        object_request_message = Message(
                                            topic=MessageTopic.OBJECT_REQUEST,
                                            body=object_response.hash,
                                        )
                                        object_request_envelope = Envelope(
                                            message=object_request_message,
                                            sender=self.relay_public_key,
                                        )
                                        self.outgoing_queue.put(
                                            (
                                                object_request_envelope.to_bytes(),
                                                (nearest_peer_ip, nearest_peer_port),
                                            )
                                        )

          
                        except Exception as e:
                            print(f"Error processing OBJECT_RESPONSE: {e}")

            except Exception as e:
                print(f"Error processing message: {e}")
    
    def _relay_outgoing_queue_processor(self):
        while True:
            try:
                data, addr = self.outgoing_queue.get()
                self.outgoing_socket.sendto(data, addr)
            except Exception as e:
                print(f"Error sending message: {e}")
    
    def _relay_peer_manager(self):
        while True:
            try:
                time.sleep(60)
                for peer in self.peers.values():
                    if (datetime.now(timezone.utc) - peer.timestamp).total_seconds() > 900:
                        del self.peers[peer.sender]
                        self.peer_route.remove_peer(peer.sender)
                        if peer.sender in self.validation_route.buckets:
                            self.validation_route.remove_peer(peer.sender)
            except Exception as e:
                print(f"Error in _peer_manager_thread: {e}")

    def _send_ping(self, addr: Tuple[str, int]):
        is_validator_flag = encode([1] if self.validation_secret_key else [0])
        ping_message = Message(topic=MessageTopic.PING, body=is_validator_flag)
        ping_envelope = Envelope(message=ping_message, sender=self.relay_public_key)
        self.outgoing_queue.put((ping_envelope.to_bytes(), addr))

    def _get_closest_local_peer(self, hash: bytes) -> Optional[Tuple[X25519PublicKey, Peer]]:
        # Find the globally closest peer using XOR distance
        closest_peer = None
        closest_distance = None
        
        # Check all peers
        for peer_key, peer in self.peers.items():
            # Calculate XOR distance between hash and peer's public key
            peer_bytes = peer_key.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
            # XOR each byte and sum them to get a total distance
            distance = sum(a ^ b for a, b in zip(hash, peer_bytes))
            # Update the closest peer if the distance is smaller
            if closest_distance is None or distance < closest_distance:
                closest_distance = distance
                closest_peer = (peer_key, peer)
        
        return closest_peer

    def _is_closer_than_local_peers(self, hash: bytes, foreign_peer_public_key: X25519PublicKey) -> bool:

        # Get the closest local peer
        closest_local_peer = self._get_closest_local_peer(hash)
        
        # If we have no local peers, the foreign peer is closer by default
        if closest_local_peer is None:
            return True
        
        # Calculate XOR distance for the foreign peer
        foreign_peer_bytes = foreign_peer_public_key.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
        foreign_distance = sum(a ^ b for a, b in zip(hash, foreign_peer_bytes))
        
        # Get the closest local peer key and calculate its distance
        closest_peer_key, _ = closest_local_peer
        closest_peer_bytes = closest_peer_key.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
        local_distance = sum(a ^ b for a, b in zip(hash, closest_peer_bytes))
        
        # Return True if the foreign peer is closer (has smaller XOR distance)
        return foreign_distance < local_distance

    # MACHINE
    def _machine_setup(self):
        self.environments: Dict[uuid.UUID, Env] = {}
        self.machine_environments_lock = threading.Lock()

    def machine_create_environment(self, parent_id: Optional[uuid.UUID] = None) -> uuid.UUID:
        env_id = uuid.uuid4()
        with self.machine_environments_lock:
            while env_id in self.environments:
                env_id = uuid.uuid4()
            self.environments[env_id] = Env(parent_id=parent_id)
        return env_id
    
    def machine_get_or_create_environment(
        self,
        env_id: Optional[uuid.UUID] = None,
        parent_id: Optional[uuid.UUID] = None,
        max_exprs: Optional[int] = None
    ) -> uuid.UUID:
        with self.machine_environments_lock:
            if env_id is not None and env_id in self.environments:
                return env_id
            new_id = env_id if env_id is not None else uuid.uuid4()
            while new_id in self.environments:
                new_id = uuid.uuid4()
            self.environments[new_id] = Env(parent_id=parent_id, max_exprs=max_exprs)
            return new_id

    def machine_delete_environment(self, env_id: uuid.UUID) -> bool:
        with self.machine_environments_lock:
            removed = self.environments.pop(env_id, None)
        return removed is not None

    def machine_expr_get(self, env_id: uuid.UUID, name: str) -> Optional[Expr]:
        with self.machine_environments_lock:
            cur = self.environments.get(env_id)
            while cur is not None:
                if name in cur.data:
                    return cur.data[name]
                if cur.parent_id:
                    cur = self.environments.get(cur.parent_id)
                else:
                    cur = None
        return None
        
    def machine_expr_put(self, env_id: uuid.UUID, name: str, expr: Expr):
        with self.machine_environments_lock:
            env = self.environments.get(env_id)
        if env is None:
            return False
        env.put(name, expr)
        return True

    def machine_expr_eval(self, env_id: uuid.UUID, expr: Expr) -> Expr:
        if isinstance(expr, Expr.Boolean) or isinstance(expr, Expr.Integer) or isinstance(expr, Expr.String) or isinstance(expr, Expr.Error):
            return expr
        
        elif isinstance(expr, Expr.Symbol):
            value = self.machine_expr_get(env_id=env_id, name=expr.value)
            if value:
                return value
            else:
                return Expr.Error(message=f"unbound symbol '{expr.value}'", origin=expr)
        
        elif isinstance(expr, Expr.ListExpr):
            if len(expr.elements) == 0:
                return expr 
            if len(expr.elements) == 1:
                return self.machine_expr_eval(expr=expr.elements[0], env_id=env_id)
            first = expr.elements[0]
            if isinstance(first, Expr.Symbol):
                first_symbol_value = self.machine_expr_get(env_id=env_id, name=first.value)
                
                if first_symbol_value and not isinstance(first_symbol_value, Expr.Function):
                    evaluated_elements = [self.machine_expr_eval(env_id=env_id, expr=e) for e in expr.elements]
                    return Expr.ListExpr(evaluated_elements)
                
                elif first.value == "def":
                    args = expr.elements[1:]
                    if len(args) != 2:
                        return Expr.Error(message=f"'def' expects exactly 2 arguments, got {len(args)}", origin=expr)
                    if not isinstance(args[0], Expr.Symbol):
                        return Expr.Error(message="first argument to 'def' must be a symbol", origin=args[0])
                    result = self.machine_expr_eval(env_id=env_id, expr=args[1])
                    if isinstance(result, Expr.Error):
                        return result
                    
                    self.machine_expr_put(env_id=env_id, name=args[0].value, expr=result)
                    return result

                # # List
                # elif first.value == "list.new":
                #     return Expr.ListExpr([self.evaluate_expression(arg, env) for arg in expr.elements[1:]])

                # elif first.value == "list.get":
                #     args = expr.elements[1:]
                #     if len(args) != 2:
                #         return Expr.Error(
                #             category="SyntaxError",
                #             message="list.get expects exactly two arguments: a list and an index"
                #         )
                #     list_obj = self.evaluate_expression(args[0], env)
                #     index = self.evaluate_expression(args[1], env)
                #     return handle_list_get(self, list_obj, index, env)

                # elif first.value == "list.insert":
                #     args = expr.elements[1:]
                #     if len(args) != 3:
                #         return Expr.ListExpr([
                #             Expr.ListExpr([]),
                #             Expr.String("list.insert expects exactly three arguments: a list, an index, and a value")
                #         ])
                    
                #     return handle_list_insert(
                #         list=self.evaluate_expression(args[0], env),
                #         index=self.evaluate_expression(args[1], env),
                #         value=self.evaluate_expression(args[2], env),
                #     )

                # elif first.value == "list.remove":
                #     args = expr.elements[1:]
                #     if len(args) != 2:
                #         return Expr.ListExpr([
                #             Expr.ListExpr([]),
                #             Expr.String("list.remove expects exactly two arguments: a list and an index")
                #         ])
                    
                #     return handle_list_remove(
                #         list=self.evaluate_expression(args[0], env),
                #         index=self.evaluate_expression(args[1], env),
                #     )

                # elif first.value == "list.length":
                #     args = expr.elements[1:]
                #     if len(args) != 1:
                #         return Expr.ListExpr([
                #             Expr.ListExpr([]),
                #             Expr.String("list.length expects exactly one argument: a list")
                #         ])
                    
                #     list_obj = self.evaluate_expression(args[0], env)
                #     if not isinstance(list_obj, Expr.ListExpr):
                #         return Expr.ListExpr([
                #             Expr.ListExpr([]),
                #             Expr.String("Argument must be a list")
                #         ])
                    
                #     return Expr.ListExpr([
                #         Expr.Integer(len(list_obj.elements)),
                #         Expr.ListExpr([]) 
                #     ])

                # elif first.value == "list.fold":
                #     if len(args) != 3:
                #         return Expr.ListExpr([
                #             Expr.ListExpr([]),
                #             Expr.String("list.fold expects exactly three arguments: a list, an initial value, and a function")
                #         ])
                    
                #     return handle_list_fold(
                #         machine=self,
                #         list=self.evaluate_expression(args[0], env),
                #         initial=self.evaluate_expression(args[1], env),
                #         func=self.evaluate_expression(args[2], env),
                #         env=env,
                #     )

                # elif first.value == "list.map":
                #     if len(args) != 2:
                #         return Expr.ListExpr([
                #             Expr.ListExpr([]),
                #             Expr.String("list.map expects exactly two arguments: a list and a function")
                #         ])
                    
                #     return handle_list_map(
                #         machine=self,
                #         list=self.evaluate_expression(args[0], env),
                #         func=self.evaluate_expression(args[1], env),
                #         env=env,
                #     )

                # elif first.value == "list.position":
                #     if len(args) != 2:
                #         return Expr.ListExpr([
                #             Expr.ListExpr([]),
                #             Expr.String("list.position expects exactly two arguments: a list and a function")
                #         ])
                    
                #     return handle_list_position(
                #         machine=self,
                #         list=self.evaluate_expression(args[0], env),
                #         predicate=self.evaluate_expression(args[1], env),
                #         env=env,
                #     )

                # elif first.value == "list.any":
                #     if len(args) != 2:
                #         return Expr.ListExpr([
                #             Expr.ListExpr([]),
                #             Expr.String("list.any expects exactly two arguments: a list and a function")
                #         ])
                    
                #     return handle_list_any(
                #         machine=self,
                #         list=self.evaluate_expression(args[0], env),
                #         predicate=self.evaluate_expression(args[1], env),
                #         env=env,
                #     )

                # elif first.value == "list.all":
                #     if len(args) != 2:
                #         return Expr.ListExpr([
                #             Expr.ListExpr([]),
                #             Expr.String("list.all expects exactly two arguments: a list and a function")
                #         ])
                    
                #     return handle_list_all(
                #         machine=self,
                #         list=self.evaluate_expression(args[0], env),
                #         predicate=self.evaluate_expression(args[1], env),
                #         env=env,
                #     )

                # Integer arithmetic primitives
                elif first.value == "+":
                    args = expr.elements[1:]
                    if not args:
                        return Expr.Error("'+' expects at least 1 argument", origin=expr)
                    vals = [self.machine_expr_eval(env_id=env_id, expr=a) for a in args]
                    for v in vals:
                        if isinstance(v, Expr.Error): return v
                        if not isinstance(v, Expr.Integer):
                            return Expr.Error("'+' only accepts integer operands", origin=v)
                    return Expr.Integer(abs(vals[0].value) if len(vals) == 1
                                        else sum(v.value for v in vals))

                elif first.value == "-":
                    args = expr.elements[1:]
                    if not args:
                        return Expr.Error("'-' expects at least 1 argument", origin=expr)
                    vals = [self.machine_expr_eval(env_id=env_id, expr=a) for a in args]
                    for v in vals:
                        if isinstance(v, Expr.Error): return v
                        if not isinstance(v, Expr.Integer):
                            return Expr.Error("'-' only accepts integer operands", origin=v)
                    if len(vals) == 1:
                        return Expr.Integer(-vals[0].value)
                    result = vals[0].value
                    for v in vals[1:]:
                        result -= v.value
                    return Expr.Integer(result)

                elif first.value == "/":
                    args = expr.elements[1:]
                    if len(args) < 2:
                        return Expr.Error("'/' expects at least 2 arguments", origin=expr)
                    vals = [self.machine_expr_eval(env_id=env_id, expr=a) for a in args]
                    for v in vals:
                        if isinstance(v, Expr.Error): return v
                        if not isinstance(v, Expr.Integer):
                            return Expr.Error("'/' only accepts integer operands", origin=v)
                    result = vals[0].value
                    for v in vals[1:]:
                        if v.value == 0:
                            return Expr.Error("division by zero", origin=v)
                        if result % v.value:
                            return Expr.Error("non-exact division", origin=expr)
                        result //= v.value
                    return Expr.Integer(result)

                elif first.value == "%":
                    if len(expr.elements) != 3:
                        return Expr.Error("'%' expects exactly 2 arguments", origin=expr)
                    a = self.machine_expr_eval(env_id=env_id, expr=expr.elements[1])
                    b = self.machine_expr_eval(env_id=env_id, expr=expr.elements[2])
                    for v in (a, b):
                        if isinstance(v, Expr.Error): return v
                        if not isinstance(v, Expr.Integer):
                            return Expr.Error("'%' only accepts integer operands", origin=v)
                    if b.value == 0:
                        return Expr.Error("division by zero", origin=expr.elements[2])
                    return Expr.Integer(a.value % b.value)

                elif first.value in ("=", "!=", ">", "<", ">=", "<="):
                    args = expr.elements[1:]
                    if len(args) != 2:
                        return Expr.Error(f"'{first.value}' expects exactly 2 arguments", origin=expr)

                    left  = self.machine_expr_eval(env_id=env_id, expr=args[0])
                    right = self.machine_expr_eval(env_id=env_id, expr=args[1])

                    for v in (left, right):
                        if isinstance(v, Expr.Error):
                            return v
                        if not isinstance(v, Expr.Integer):
                            return Expr.Error(f"'{first.value}' only accepts integer operands", origin=v)

                    a, b = left.value, right.value
                    match first.value:
                        case "=":   res = a == b
                        case "!=":  res = a != b
                        case ">":   res = a >  b
                        case "<":   res = a <  b
                        case ">=":  res = a >= b
                        case "<=":  res = a <= b

                    return Expr.Boolean(res)

            else:
                evaluated_elements = [self.machine_expr_eval(env_id=env_id, expr=e) for e in expr.elements]
                return Expr.ListExpr(evaluated_elements)
            
        elif isinstance(expr, Expr.Function):
            return expr
        
        else:
            raise ValueError(f"Unknown expression type: {type(expr)}")
        
