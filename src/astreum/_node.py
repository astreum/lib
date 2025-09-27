from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Union
import uuid
import threading

from src.astreum._lispeum import Env, Expr, Meter, low_eval

# ===============================
# 1. Helpers (no decoding, two's complement)
# ===============================



def bytes_touched(*vals: bytes) -> int:
    """For metering: how many bytes were manipulated (max of operands)."""
    return max((len(v) for v in vals), default=1)

# ===============================
# 2. Structures
# ===============================

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

    # ---- Eval ----
    def high_eval(self, env_id: uuid.UUID, expr: Expr, meter = None) -> Expr:

        if meter is None:
            meter = Meter()

        # ---------- atoms ----------
        if isinstance(expr, Expr.Error):
            return expr

        if isinstance(expr, Expr.Symbol):
            bound = self.env_get(env_id, expr.value.encode())
            if bound is None:
                return Expr.Error(f"unbound symbol '{expr.value}'", origin=expr)
            return bound

        if not isinstance(expr, Expr.ListExpr):
            return expr  # Expr.Byte or other literals passthrough

        # ---------- empty / single ----------
        if len(expr.elements) == 0:
            return expr
        if len(expr.elements) == 1:
            return self.high_eval(env_id=env_id, expr=expr.elements[0], meter=meter)

        tail = expr.elements[-1]

        # ---------- (value name def) ----------
        if isinstance(tail, Expr.Symbol) and tail.value == "def":
            if len(expr.elements) < 3:
                return Expr.Error("def expects (value name def)", origin=expr)
            name_e = expr.elements[-2]
            if not isinstance(name_e, Expr.Symbol):
                return Expr.Error("def name must be symbol", origin=name_e)
            value_e = expr.elements[-3]
            value_res = self.high_eval(env_id=env_id, expr=value_e, meter=meter)
            if isinstance(value_res, Expr.Error):
                return value_res
            self.env_set(env_id, name_e.value.encode(), value_res)
            return value_res

        # ---- LOW-LEVEL call: ( arg1 arg2 ... ( (body) sk ) ) ----
        if isinstance(tail, Expr.ListExpr):
            inner = tail.elements
            if len(inner) >= 2 and isinstance(inner[-1], Expr.Symbol) and inner[-1].value == "sk":
                body_expr = inner[-2]
                if not isinstance(body_expr, Expr.ListExpr):
                    return Expr.Error("sk body must be list", origin=body_expr)

                # helper: turn an Expr into a contiguous bytes buffer
                def to_bytes(v: Expr) -> Union[bytes, Expr.Error]:
                    if isinstance(v, Expr.Byte):
                        return bytes([v.value & 0xFF])
                    if isinstance(v, Expr.ListExpr):
                        # expect a list of Expr.Byte
                        out: bytearray = bytearray()
                        for el in v.elements:
                            if isinstance(el, Expr.Byte):
                                out.append(el.value & 0xFF)
                            else:
                                return Expr.Error("byte list must contain only Byte", origin=el)
                        return bytes(out)
                    if isinstance(v, Expr.Error):
                        return v
                    return Expr.Error("argument must resolve to Byte or (Byte ...)", origin=v)

                # resolve ALL preceding args into bytes (can be Byte or List[Byte])
                args_exprs = expr.elements[:-1]
                arg_bytes: List[bytes] = []
                for a in args_exprs:
                    v = self.high_eval(env_id=env_id, expr=a, meter=meter)
                    if isinstance(v, Expr.Error):
                        return v
                    vb = to_bytes(v)
                    if isinstance(vb, Expr.Error):
                        return vb
                    arg_bytes.append(vb)

                # build low-level code with $0-based placeholders ($0 = first arg)
                code: List[bytes] = []

                def emit(tok: Expr) -> Union[None, Expr.Error]:
                    if isinstance(tok, Expr.Symbol):
                        name = tok.value
                        if name.startswith("$"):
                            idx_s = name[1:]
                            if not idx_s.isdigit():
                                return Expr.Error("invalid sk placeholder", origin=tok)
                            idx = int(idx_s)  # $0 is first
                            if idx < 0 or idx >= len(arg_bytes):
                                return Expr.Error("arity mismatch in sk placeholder", origin=tok)
                            code.append(arg_bytes[idx])
                            return None
                        code.append(name.encode())
                        return None

                    if isinstance(tok, Expr.Byte):
                        code.append(bytes([tok.value & 0xFF]))
                        return None

                    if isinstance(tok, Expr.ListExpr):
                        rv = self.high_eval(env_id, tok, meter=meter)
                        if isinstance(rv, Expr.Error):
                            return rv
                        rb = to_bytes(rv)
                        if isinstance(rb, Expr.Error):
                            return rb
                        code.append(rb)
                        return None

                    if isinstance(tok, Expr.Error):
                        return tok

                    return Expr.Error("invalid token in sk body", origin=tok)

                for t in body_expr.elements:
                    err = emit(t)
                    if isinstance(err, Expr.Error):
                        return err

                # Execute low-level code built from sk-body using the caller's meter
                res = self.low_eval(code, meter=meter)
                if isinstance(res, Expr.Error):
                    return res
                return Expr.ListExpr([Expr.Byte(b) for b in res])

        # ---------- (... (body params fn))  HIGH-LEVEL CALL ----------
        if isinstance(tail, Expr.ListExpr):
            fn_form = tail
            if (len(fn_form.elements) >= 3
                and isinstance(fn_form.elements[-1], Expr.Symbol)
                and fn_form.elements[-1].value == "fn"):

                body_expr   = fn_form.elements[-3]
                params_expr = fn_form.elements[-2]

                if not isinstance(body_expr, Expr.ListExpr):
                    return Expr.Error("fn body must be list", origin=body_expr)
                if not isinstance(params_expr, Expr.ListExpr):
                    return Expr.Error("fn params must be list", origin=params_expr)

                params: List[bytes] = []
                for p in params_expr.elements:
                    if not isinstance(p, Expr.Symbol):
                        return Expr.Error("fn param must be symbol", origin=p)
                    params.append(p.value.encode())

                args_exprs = expr.elements[:-1]
                if len(args_exprs) != len(params):
                    return Expr.Error("arity mismatch", origin=expr)

                arg_bytes: List[bytes] = []
                for a in args_exprs:
                    v = self.high_eval(env_id, a, meter=meter)
                    if isinstance(v, Expr.Error):
                        return v
                    if not isinstance(v, Expr.Byte):
                        return Expr.Error("argument must resolve to Byte", origin=a)
                    arg_bytes.append(bytes([v.value & 0xFF]))

                # child env, bind params -> Expr.Byte
                child_env = uuid.uuid4()
                self.environments[child_env] = Env(parent_id=env_id)
                for name_b, val_b in zip(params, arg_bytes):
                    self.env_set(child_env, name_b, Expr.Byte(val_b[0]))

                # evaluate HL body, metered from the top
                return self.high_eval(child_env, body_expr, meter=meter)

        # ---------- default: resolve each element and return list ----------
        resolved: List[Expr] = [self.high_eval(env_id, e, meter=meter) for e in expr.elements]
        return Expr.ListExpr(resolved)
