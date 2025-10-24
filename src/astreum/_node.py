from __future__ import annotations
from typing import Dict, Optional
import uuid
import threading

from ._storage.atom import Atom
from ._lispeum import Env, Expr, Meter, low_eval, parse, tokenize, ParseError

__all__ = [
    "Node",
    "Env",
    "Expr",
    "Meter",
    "parse",
    "tokenize",
]

def bytes_touched(*vals: bytes) -> int:
    """For metering: how many bytes were manipulated (max of operands)."""
    return max((len(v) for v in vals), default=1)

class Node:
    def __init__(self, config: dict):
        # Storage Setup
        self.in_memory_storage: Dict[bytes, Atom] = {}
        self.in_memory_storage_lock = threading.RLock()
        self.storage_index: Dict[bytes, str] = {}
        # Lispeum Setup
        self.environments: Dict[uuid.UUID, Env] = {}
        self.machine_environments_lock = threading.RLock()
        self.low_eval = low_eval
        # Communication and Validation Setup (import lazily to avoid heavy deps during parsing tests)
        try:
            from astreum._communication import communication_setup  # type: ignore
            communication_setup(node=self, config=config)
        except Exception:
            pass
        try:
            from astreum._consensus import consensus_setup  # type: ignore
            consensus_setup(node=self, config=config)
        except Exception:
            pass
        


    # ---- Env helpers ----
    def env_get(self, env_id: uuid.UUID, key: bytes) -> Optional[Expr]:
        cur = self.environments.get(env_id)
        while cur is not None:
            if key in cur.data:
                return cur.data[key]
            cur = self.environments.get(cur.parent_id) if cur.parent_id else None
        return None

    def env_set(self, env_id: uuid.UUID, key: bytes, value: Expr) -> bool:
        with self.machine_environments_lock:
            env = self.environments.get(env_id)
            if env is None:
                return False
            env.data[key] = value
            return True

    # Storage
    def _local_get(self, key: bytes) -> Optional[Atom]:
        with self.in_memory_storage_lock:
            return self.in_memory_storage.get(key)

    def _local_set(self, key: bytes, value: Atom) -> None:
        with self.in_memory_storage_lock:
            self.in_memory_storage[key] = value

    def _network_get(self, key: bytes) -> Optional[Atom]:
        # locate storage provider
        # query storage provider
        return None

    def storage_get(self, key: bytes) -> Optional[Atom]:
        """Retrieve an Atom by checking local storage first, then the network."""
        atom = self._local_get(key)
        if atom is not None:
            return atom
        return self._network_get(key)

    def _network_set(self, atom: Atom) -> None:
        """Advertise an atom to the closest known peer so they can fetch it from us."""
        try:
            from ._communication.message import Message, MessageTopic
        except Exception:
            return

        atom_id = atom.object_id()
        try:
            closest_peer = self.peer_route.closest_peer_for_hash(atom_id)
        except Exception:
            return
        if closest_peer is None or closest_peer.address is None:
            return
        target_addr = closest_peer.address

        try:
            provider_ip, provider_port = self.incoming_socket.getsockname()[:2]
        except Exception:
            return

        provider_str = f"{provider_ip}:{int(provider_port)}"
        try:
            provider_bytes = provider_str.encode("utf-8")
        except Exception:
            return

        payload = atom_id + provider_bytes
        message = Message(topic=MessageTopic.STORAGE_REQUEST, content=payload)
        self.outgoing_queue.put((message.to_bytes(), target_addr))
