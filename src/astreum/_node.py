from __future__ import annotations
from typing import Dict, Optional
import uuid
import threading

from src.astreum._storage.atom import Atom
from src.astreum._lispeum import Env, Expr, low_eval, parse, tokenize, ParseError

def bytes_touched(*vals: bytes) -> int:
    """For metering: how many bytes were manipulated (max of operands)."""
    return max((len(v) for v in vals), default=1)

class Node:
    def __init__(self, config: dict):
        # Storage Setup
        self.in_memory_storage: Dict[bytes, Atom] = {}
        self.in_memory_storage_lock = threading.RLock()
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
            consensus_setup(node=self)
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
