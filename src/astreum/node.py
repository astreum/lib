import socket
import threading
import time
from queue import Queue
from pathlib import Path
from typing import Tuple, Dict, Union, Optional, List
from datetime import datetime, timedelta, timezone
import uuid

from astreum.lispeum.environment import Env
from astreum.lispeum.expression import Expr
from astreum.relay.peer import Peer
from astreum.relay.route import Route
from astreum.relay.setup import load_ed25519, load_x25519, make_routes, setup_outgoing, setup_udp
from astreum.storage.object import ObjectRequest, ObjectRequestType, ObjectResponse, ObjectResponseType
from astreum.storage.setup import storage_setup

from .models.transaction import Transaction
from .format import encode, decode
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives import serialization
from .crypto import ed25519, x25519
import blake3
import struct
from .models.message import Message, MessageTopic

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

class Node:
    def __init__(self, config: dict = {}):
        self._machine_setup()
        machine_only = bool(config.get('machine-only', True))
        if not machine_only:
            (
                self.storage_path,
                self.memory_storage,
                self.storage_get_relay_timeout,
                self.storage_index
            ) = storage_setup(config)

            self._relay_setup(config=config)
            self._validation_setup(config=config)

    def _validation_setup(self, config: dict):
        if True:
            self.validator_transactions: Dict[bytes, Transaction] = {}
            # validator thread
        pass

    def _create_block(self):
        pass

    def _relay_setup(self, config: dict):
        self.use_ipv6              = config.get('use_ipv6', False)

        # key loading
        self.relay_secret_key      = load_x25519(config.get('relay_secret_key'))
        self.validation_secret_key = load_ed25519(config.get('validation_secret_key'))

        # derive pubs + routes
        self.relay_public_key      = self.relay_secret_key.public_key()
        self.peer_route, self.validation_route = make_routes(
            self.relay_public_key,
            self.validation_secret_key
        )

        # sockets + queues + threads
        (self.incoming_socket,
         self.incoming_port,
         self.incoming_queue,
         self.incoming_populate_thread,
         self.incoming_process_thread
        ) = setup_udp(config.get('incoming_port', 7373), self.use_ipv6)

        (self.outgoing_socket,
         self.outgoing_queue,
         self.outgoing_thread
        ) = setup_outgoing(self.use_ipv6)

        # other workers & maps
        self.object_request_queue = Queue()
        self.peer_manager_thread  = threading.Thread(
            target=self._relay_peer_manager,
            daemon=True
        )
        self.peer_manager_thread.start()

        self.peers, self.addresses = {}, {} # peers: Dict[X25519PublicKey,Peer], addresses: Dict[(str,int),X25519PublicKey]

        # bootstrap pings
        for addr in config.get('bootstrap', []):
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
            object_request_message = Message(topic=MessageTopic.OBJECT_REQUEST, content=hash)
            self.outgoing_queue.put((object_request_message.to_bytes(), self.peers[closest_peer].address))

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
                message = Message.from_bytes(data)
                match message.topic:
                    case MessageTopic.PING:
                        peer_pub_key = self.addresses.get(addr)
                        if peer_pub_key in self.peers:
                            self.peers[peer_pub_key].timestamp = datetime.now(timezone.utc)
                            continue

                        is_validator_flag = decode(message.body)

                        if peer_pub_key not in self.peers:
                            self._send_ping(addr)

                        peer = Peer(my_sec_key=self.relay_secret_key, peer_pub_key=peer_pub_key)
                        self.peers[peer.sender] = peer
                        self.peer_route.add_peer(peer_pub_key)
                        if is_validator_flag == [1]:
                            self.validation_route.add_peer(peer_pub_key)

                        if peer.timestamp < datetime.now(timezone.utc) - timedelta(minutes=5.0):
                            self._send_ping(addr)
                    
                    case MessageTopic.OBJECT_REQUEST:
                        try:
                            object_request = ObjectRequest.from_bytes(message.body)

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
                                        obj_res_msg  = Message(topic=MessageTopic.OBJECT_RESPONSE, body=resp.to_bytes())
                                        self.outgoing_queue.put((obj_res_msg.to_bytes(), addr))
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
                                        obj_res_msg = Message(topic=MessageTopic.OBJECT_RESPONSE, body=resp.to_bytes())
                                        self.outgoing_queue.put((obj_res_msg.to_bytes(), addr))
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
                                        obj_res_msg = Message(topic=MessageTopic.OBJECT_RESPONSE, body=resp.to_bytes())
                                        self.outgoing_queue.put((obj_res_msg.to_bytes(), addr))

                                # --------------  OBJECT_PUT  --------------
                                case ObjectRequestType.OBJECT_PUT:
                                    # Ensure the hash is present / correct.
                                    obj_hash = object_request.hash or blake3.blake3(object_request.data).digest()

                                    nearest = self._get_closest_local_peer(obj_hash)
                                    # If a strictly nearer peer exists, forward the PUT.
                                    if nearest and self._is_closer_than_local_peers(obj_hash, nearest[0]):
                                        fwd_req = ObjectRequest(
                                            type=ObjectRequestType.OBJECT_PUT,
                                            data=object_request.data,
                                            hash=obj_hash
                                        )
                                        obj_req_msg = Message(topic=MessageTopic.OBJECT_REQUEST, body=fwd_req.to_bytes())
                                        self.outgoing_queue.put((obj_req_msg.to_bytes(), nearest[1].address))
                                    else:
                                        # We are closest → remember who can provide the object.
                                        peer_pub_key = self.addresses.get(addr)
                                        provider_record = encode([
                                           peer_pub_key.public_bytes(),
                                            encode_ip_address(*addr)
                                        ])
                                        if not hasattr(self, "storage_index") or not isinstance(self.storage_index, dict):
                                            self.storage_index = {}
                                        self.storage_index[obj_hash] = provider_record

                        except Exception as e:
                            print(f"Error processing OBJECT_REQUEST: {e}")

                    case MessageTopic.OBJECT_RESPONSE:
                        try:
                            object_response = ObjectResponse.from_bytes(message.body)
                            if object_response.hash not in self.object_request_queue:
                                continue
                            
                            match object_response.type:
                                case ObjectResponseType.OBJECT_FOUND:
                                    if object_response.hash != blake3.blake3(object_response.data).digest():
                                        continue
                                    self.object_request_queue.remove(object_response.hash)
                                    self._local_object_put(object_response.hash, object_response.data)

                                case ObjectResponseType.OBJECT_PROVIDER:
                                    _provider_public_key, provider_address = decode(object_response.data)
                                    provider_ip, provider_port = decode_ip_address(provider_address)
                                    obj_req_msg = Message(topic=MessageTopic.OBJECT_REQUEST, body=object_hash)
                                    self.outgoing_queue.put((obj_req_msg.to_bytes(), (provider_ip, provider_port)))

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
                                        nearest_peer_ip, nearest_peer_port = decode_ip_address(nearest_peer_address)
                                        obj_req_msg = Message(topic=MessageTopic.OBJECT_REQUEST, content=object_response.hash)
                                        self.outgoing_queue.put((obj_req_msg.to_bytes(), (nearest_peer_ip, nearest_peer_port),)
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
        ping_message = Message(topic=MessageTopic.PING, content=is_validator_flag)
        self.outgoing_queue.put((ping_message.to_bytes(), addr))

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
                        return Expr.Error("def expects key value", origin=expr)
                    if not isinstance(args[0], Expr.Symbol):
                        return Expr.Error(message="first argument to 'def' must be a symbol", origin=args[0])
                    result = self.machine_expr_eval(env_id=env_id, expr=args[1])
                    if isinstance(result, Expr.Error):
                        return result
                    
                    self.machine_expr_put(env_id=env_id, name=args[0].value, expr=result)
                    return result


                ## DEF: (def x 1) -> ()

                ## GET: (x) -> 1

                ## ADD: (+ 1 2) -> (+ 3) -> 3

                ## NAND: (~& 1 1) -> (~& 0) -> 0

                ## 


                ## List: ints -> (1 2)
                # push: (list.push 3 ints) -> (1 2 3) / (list.push 0 0 ints) -> (0 1 2)
                elif first.value == "list.push":
                    args = expr.elements[1:]
                    if len(args) == 2:
                        val_expr, list_expr = args
                        idx = None
                    elif len(args) == 3:
                        idx_expr, val_expr, list_expr = args
                        idx = self.machine_expr_eval(env_id, idx_expr)
                        if isinstance(idx, Expr.Error): return idx
                        if not isinstance(idx, Expr.IntExpr):
                            return Expr.Error("index must be int", origin=idx_expr)
                        idx = idx.value
                    else:
                        return Expr.Error("list.push expects (value list) or (index value list)", origin=expr)

                    lst = self.machine_expr_eval(env_id, list_expr)
                    if isinstance(lst, Expr.Error): return lst
                    if not isinstance(lst, Expr.ListExpr):
                        return Expr.Error("last arg to list.push must be a list", origin=list_expr)

                    val = self.machine_expr_eval(env_id, val_expr)
                    if isinstance(val, Expr.Error): return val

                    elems = list(lst.elements)
                    if idx is None:
                        elems.append(val)
                    else:
                        if idx < 0 or idx > len(elems):
                            return Expr.Error("index out of range", origin=idx_expr)
                        elems.insert(idx, val)
                    return Expr.ListExpr(elems)

                # pop: (list.pop 1 ints) -> 2
                elif first.value == "list.pop":
                    if len(expr.elements) < 3:
                        return Expr.Error("list.pop expects index list", origin=expr)

                    idx_expr, list_expr = expr.elements[1], expr.elements[2]
                    idx = self.machine_expr_eval(env_id, idx_expr)
                    if isinstance(idx, Expr.Error): return idx
                    if not isinstance(idx, Expr.IntExpr):
                        return Expr.Error("index must be int", origin=idx_expr)
                    idx = idx.value

                    lst = self.machine_expr_eval(env_id, list_expr)
                    if isinstance(lst, Expr.Error): return lst
                    if not isinstance(lst, Expr.ListExpr):
                        return Expr.Error("second arg to list.pop must be a list", origin=list_expr)

                    elems = list(lst.elements)
                    if idx < 0 or idx >= len(elems):
                        return Expr.Error("index out of range", origin=idx_expr)
                    del elems[idx]
                    return Expr.ListExpr(elems)

                # get: (list.get 1 ints) -> 2
                elif first.value == "list.get":
                    if len(expr.elements) < 3:
                        return Expr.Error("list.get expects index list", origin=expr)

                    idx_expr, list_expr = expr.elements[1], expr.elements[2]
                    idx = self.machine_expr_eval(env_id, idx_expr)
                    if isinstance(idx, Expr.Error): return idx
                    if not isinstance(idx, Expr.IntExpr):
                        return Expr.Error("index must be int", origin=idx_expr)
                    idx = idx.value

                    lst = self.machine_expr_eval(env_id, list_expr)
                    if isinstance(lst, Expr.Error): return lst
                    if not isinstance(lst, Expr.ListExpr):
                        return Expr.Error("second arg to list.get must be a list", origin=list_expr)

                    if idx < 0 or idx >= len(lst.elements):
                        return Expr.Error("index out of range", origin=idx_expr)
                    return lst.elements[idx]

                # set: (list.set 1 3 ints) -> (1 3)
                elif first.value == "list.set":
                    if len(expr.elements) < 4:
                        return Expr.Error("list.set expects index value list", origin=expr)
                    idx_expr, val_expr, list_expr = expr.elements[1], expr.elements[2], expr.elements[3]
                    idx = self.machine_expr_eval(env_id, idx_expr)
                    if isinstance(idx, Expr.Error): return idx
                    if not isinstance(idx, Expr.IntExpr):
                        return Expr.Error("index must be int", origin=idx_expr)
                    idx = idx.value

                    val = self.machine_expr_eval(env_id, val_expr)
                    if isinstance(val, Expr.Error): return val

                    lst = self.machine_expr_eval(env_id, list_expr)
                    if isinstance(lst, Expr.Error): return lst
                    if not isinstance(lst, Expr.ListExpr):
                        return Expr.Error("third arg to list.set must be a list", origin=list_expr)

                    elems = list(lst.elements)
                    if idx < 0 or idx >= len(elems):
                        return Expr.Error("index out of range", origin=idx_expr)
                    elems[idx] = val
                    return Expr.ListExpr(elems)

                ### each: (list.each fn list) -> ()
                elif first.value == "list.each":
                    if len(expr.elements) < 3:
                        return Expr.Error("list.each expects fn list", origin=expr)
                    fn_expr, list_expr = expr.elements[1], expr.elements[2]
                    lst = self.machine_expr_eval(env_id, list_expr)
                    if isinstance(lst, Expr.Error):
                        return lst
                    if not isinstance(lst, Expr.ListExpr):
                        return Expr.Error("second arg to list.each must be a list", origin=list_expr)

                    for el in lst.elements:
                        res = self.machine_expr_eval(env_id, Expr.ListExpr([fn_expr, el]))
                        if isinstance(res, Expr.Error):
                            return res
                    return Expr.ListExpr([])

                ### fold: (list.fold fn init list) / (list.fold + 0 ints) -> 3
                elif first.value == "list.fold":
                    fn_expr, init_expr, list_expr = expr.elements[1], expr.elements[2], expr.elements[3]
                    acc = self.machine_expr_eval(env_id, init_expr)
                    if isinstance(acc, Expr.Error):
                        return acc

                    lst = self.machine_expr_eval(env_id, list_expr)
                    if isinstance(lst, Expr.Error):
                        return lst
                    if not isinstance(lst, Expr.ListExpr):
                        return Expr.Error("third arg to list.fold must be a list", origin=list_expr)

                    for el in lst.elements:
                        call = Expr.ListExpr([fn_expr, acc, el])
                        res = self.machine_expr_eval(env_id, call)
                        if isinstance(res, Expr.Error):
                            return res
                        acc = res

                    return acc

                ### sort: (list.sort fn list) / (list.sort (fn (a b) (a < b)) ints) -> (2 1)
                elif first.value == "list.sort":
                    if len(expr.elements) < 3:
                        return Expr.Error("list.sort fn list", origin=expr)
                    fn_e, lst_e = expr.elements[1], expr.elements[2]

                    lst = self.machine_expr_eval(env_id, lst_e)
                    if isinstance(lst, Expr.Error): return lst
                    if not isinstance(lst, Expr.ListExpr):
                        return Expr.Error("second arg must be list", origin=lst_e)

                    elems = list(lst.elements)
                    for i in range(1, len(elems)):
                        j = i
                        while j > 0:
                            cmp_res = self.machine_expr_eval(
                                env_id,
                                Expr.ListExpr([fn_e, elems[j-1], elems[j]])
                            )
                            if isinstance(cmp_res, Expr.Error): return cmp_res
                            if not isinstance(cmp_res, Expr.BoolExpr):
                                return Expr.Error("comparator must return bool", origin=fn_e)

                            if cmp_res.value:
                                elems[j-1], elems[j] = elems[j], elems[j-1]
                                j -= 1
                            else:
                                break
                    return Expr.ListExpr(elems)

                ### len: (list.len list) -> Int / (list.len ints) -> Integer(2)
                elif first.value == "list.len":
                    if len(expr.elements) < 2:
                        return Expr.Error("list.len list", origin=expr)
                    lst_e = expr.elements[1]
                    lst = self.machine_expr_eval(env_id, lst_e)
                    if isinstance(lst, Expr.Error): return lst
                    if not isinstance(lst, Expr.ListExpr):
                        return Expr.Error("arg must be list", origin=lst_e)
                    return Expr.Integer(len(lst.elements))

                ## Integer
                ### add
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

            if isinstance(first, Expr.Function):
                arg_exprs = expr.elements[1:]
                if len(arg_exprs) != len(first.params):
                    return Expr.Error(f"arity mismatch: expected {len(first.params)}, got {len(arg_exprs)}", origin=expr)

                call_env = self.machine_create_environment(parent_id=env_id)
                for name, aexpr in zip(first.params, arg_exprs):
                    val = self.machine_expr_eval(env_id, aexpr)
                    if isinstance(val, Expr.Error): return val
                    self.machine_expr_put(call_env, name, val)

                return self.machine_expr_eval(env_id=call_env, expr=first.body)

            else:
                evaluated_elements = [self.machine_expr_eval(env_id=env_id, expr=e) for e in expr.elements]
                return Expr.ListExpr(evaluated_elements)
            
        elif isinstance(expr, Expr.Function):
            return expr
        
        else:
            raise ValueError(f"Unknown expression type: {type(expr)}")
        
