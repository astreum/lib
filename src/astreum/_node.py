from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Union
import uuid
import threading

from src.astreum._lispeum import Env, Expr, Meter, low_eval

def bytes_touched(*vals: bytes) -> int:
    """For metering: how many bytes were manipulated (max of operands)."""
    return max((len(v) for v in vals), default=1)

from blake3 import blake3

ZERO32 = b"\x00"*32

def u64_le(n: int) -> bytes:
    return int(n).to_bytes(8, "little", signed=False)

def hash_bytes(b: bytes) -> bytes:
    return blake3(b).digest()

class Atom:
    data: bytes
    next: bytes
    size: int

    def __init__(self, data: bytes, next: bytes = ZERO32, size: Optional[int] = None):
        self.data = data
        self.next = next
        self.size = len(data) if size is None else size

    @staticmethod
    def from_data(data: bytes, next_hash: bytes = ZERO32) -> "Atom":
        return Atom(data=data, next=next_hash, size=len(data))

    @staticmethod
    def object_id_from_parts(data_hash: bytes, next_hash: bytes, size: int) -> bytes:
        return blake3(data_hash + next_hash + u64_le(size)).digest()

    def data_hash(self) -> bytes:
        return hash_bytes(self.data)

    def object_id(self) -> bytes:
        return self.object_id_from_parts(self.data_hash(), self.next, self.size)

    @staticmethod
    def verify_metadata(object_id: bytes, size: int, next_hash: bytes, data_hash: bytes) -> bool:
        return object_id == blake3(data_hash + next_hash + u64_le(size)).digest()

    def to_bytes(self) -> bytes:
        if len(self.next) != len(ZERO32):
            raise ValueError("next must be 32 bytes")
        return self.next + self.data

    @staticmethod
    def from_bytes(buf: bytes) -> "Atom":
        if len(buf) < len(ZERO32):
            raise ValueError("buffer too short for Atom header")
        next_hash = buf[:len(ZERO32)]
        data = buf[len(ZERO32):]
        return Atom(data=data, next=next_hash, size=len(data))

def u32_le(n: int) -> bytes:
    return int(n).to_bytes(4, "little", signed=False)

def expr_to_atoms(e: Expr) -> Tuple[bytes, List[Atom]]:
    def sym(v: str) -> Tuple[bytes, List[Atom]]:
        val = v.encode("utf-8")
        val_atom = Atom.from_data(u32_le(len(val)) + val)
        typ_atom = Atom.from_data(b"symbol", val_atom.object_id())
        return typ_atom.object_id(), [val_atom, typ_atom]

    def byt(v: int) -> Tuple[bytes, List[Atom]]:
        val_atom = Atom.from_data(bytes([v & 0xFF]))
        typ_atom = Atom.from_data(b"byte", val_atom.object_id())
        return typ_atom.object_id(), [val_atom, typ_atom]

    def err(topic: str, origin: Optional[Expr]) -> Tuple[bytes, List[Atom]]:
        t = topic.encode("utf-8")
        origin_hash, acc = (ZERO32, [])
        if origin is not None:
            origin_hash, acc = expr_to_atoms(origin)
        val_atom = Atom.from_data(u32_le(len(t)) + t + origin_hash)
        typ_atom = Atom.from_data(b"error", val_atom.object_id())
        return typ_atom.object_id(), acc + [val_atom, typ_atom]

    def lst(items: List[Expr]) -> Tuple[bytes, List[Atom]]:
        acc: List[Atom] = []
        child_hashes: List[bytes] = []
        for it in items:
            h, atoms = expr_to_atoms(it)
            acc.extend(atoms)
            child_hashes.append(h)
        next_hash = ZERO32
        elem_atoms: List[Atom] = []
        for h in reversed(child_hashes):
            a = Atom.from_data(h, next_hash)
            next_hash = a.object_id()
            elem_atoms.append(a)
        elem_atoms.reverse()
        head = next_hash
        val_atom = Atom.from_data(u64_le(len(items)), head)
        typ_atom = Atom.from_data(b"list", val_atom.object_id())
        return typ_atom.object_id(), acc + elem_atoms + [val_atom, typ_atom]

    if isinstance(e, Expr.Symbol):
        return sym(e.value)
    if isinstance(e, Expr.Byte):
        return byt(e.value)
    if isinstance(e, Expr.Error):
        return err(e.topic, e.origin)
    if isinstance(e, Expr.ListExpr):
        return lst(e.elements)
    raise TypeError("unknown Expr variant")

class Node:
    def __init__(self):
        # Storage Setup
        self.in_memory_storage: Dict[bytes, bytes] = {}
        # Lispeum Setup
        self.environments: Dict[uuid.UUID, Env] = {}
        self.machine_environments_lock = threading.RLock()
        self.low_eval = low_eval

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

    # ---- Storage (persistent) ----
    def _local_get(self, key: bytes) -> Optional[bytes]:
        return self.in_memory_storage.get(key)

    def _local_set(self, key: bytes, value: bytes) -> None:
        self.in_memory_storage[key] = value
