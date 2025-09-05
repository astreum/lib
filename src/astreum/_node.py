from __future__ import annotations
from typing import Dict, List, Optional, Union
import uuid
import threading

# ===============================
# 1. Helpers (no decoding, two's complement)
# ===============================

def tc_to_int(b: bytes) -> int:
    """bytes -> int using two's complement (width = len(b)*8)."""
    if not b:
        return 0
    return int.from_bytes(b, "big", signed=True)

def int_to_tc(n: int, width_bytes: int) -> bytes:
    """int -> bytes (two's complement, fixed width)."""
    if width_bytes <= 0:
        return b"\x00"
    return n.to_bytes(width_bytes, "big", signed=True)

def min_tc_width(n: int) -> int:
    """minimum bytes to store n in two's complement."""
    if n == 0:
        return 1
    w = 1
    while True:
        try:
            n.to_bytes(w, "big", signed=True)
            return w
        except OverflowError:
            w += 1

def nand_bytes(a: bytes, b: bytes) -> bytes:
    """Bitwise NAND on two byte strings, zero-extending to max width."""
    w = max(len(a), len(b), 1)
    au = int.from_bytes(a.rjust(w, b"\x00"), "big", signed=False)
    bu = int.from_bytes(b.rjust(w, b"\x00"), "big", signed=False)
    mask = (1 << (w * 8)) - 1
    resu = (~(au & bu)) & mask
    return resu.to_bytes(w, "big", signed=False)

def bytes_touched(*vals: bytes) -> int:
    """For metering: how many bytes were manipulated (max of operands)."""
    return max((len(v) for v in vals), default=1)

# ===============================
# 2. Structures
# ===============================

class Expr:
    class ListExpr:
        def __init__(self, elements: List['Expr']):
            self.elements = elements
        
        def __repr__(self):
            if not self.elements:
                return "()"
            inner = " ".join(str(e) for e in self.elements)
            return f"({inner})"
        
    class Symbol:
        def __init__(self, value: str):
            self.value = value

        def __repr__(self):
            return self.value
        
    class Byte:
        def __init__(self, value: int):
            self.value = value

        def __repr__(self):
            return self.value
        
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
    ):
        self.data: Dict[bytes, Expr] = {} if data is None else data
        self.parent_id = parent_id

class Meter:
    def __init__(self, enabled: bool = True, limit: Optional[int] = None):
        self.enabled = enabled
        self.limit: Optional[int] = limit
        self.used: int = 0

    def charge_bytes(self, n: int) -> bool:
        if not self.enabled:
            return True
        if n < 0:
            n = 0
        if self.limit is not None and (self.used + n) >= self.limit:
            return False
        self.used += n
        return True

class Node:
    def __init__(self):
        self.environments: Dict[uuid.UUID, Env] = {}
        self.in_memory_storage: Dict[bytes, bytes] = {}
        self.machine_environments_lock = threading.RLock()

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
    def low_eval(self, code: List[bytes], meter: Meter) -> Union[bytes, Expr.Error]:
        
        heap: Dict[bytes, bytes] = {}

        stack: List[bytes] = []
        pc = 0

        while True:
            if pc >= len(code):
                if len(stack) != 1:
                    return Expr.Error("bad stack")
                return stack.pop()

            tok = code[pc]
            pc += 1

            # ---------- ADD ----------
            if tok == b"add":
                if len(stack) < 2:
                    return Expr.Error("underflow")
                b_b = stack.pop()
                a_b = stack.pop()
                a_i = tc_to_int(a_b)
                b_i = tc_to_int(b_b)
                res_i = a_i + b_i
                width = max(len(a_b), len(b_b), min_tc_width(res_i))
                res_b = int_to_tc(res_i, width)
                # charge for both operands' byte widths
                if not meter.charge_bytes(len(a_b) + len(b_b)):
                    return Expr.Error("meter limit")
                stack.append(res_b)
                continue

            # ---------- NAND ----------
            if tok == b"nand":
                if len(stack) < 2:
                    return Expr.Error("underflow")
                b_b = stack.pop()
                a_b = stack.pop()
                res_b = nand_bytes(a_b, b_b)
                # bitwise cost: 2 * max(len(a), len(b))
                if not meter.charge_bytes(2 * max(len(a_b), len(b_b), 1)):
                    return Expr.Error("meter limit")
                stack.append(res_b)
                continue

            # ---------- JUMP ----------
            if tok == b"jump":
                if len(stack) < 1:
                    return Expr.Error("underflow")
                tgt_b = stack.pop()
                if not meter.charge_bytes(1):
                    return Expr.Error("meter limit")
                tgt_i = tc_to_int(tgt_b)
                if tgt_i < 0 or tgt_i >= len(code):
                    return Expr.Error("bad jump")
                pc = tgt_i
                continue

            # ---------- HEAP GET ----------
            if tok == b"heap_get":
                if len(stack) < 1:
                    return Expr.Error("underflow")
                key = stack.pop()
                val = heap.get(key) or b""
                # get cost: 1
                if not meter.charge_bytes(1):
                    return Expr.Error("meter limit")
                stack.append(val)
                continue

            # ---------- HEAP SET ----------
            if tok == b"heap_set":
                if len(stack) < 2:
                    return Expr.Error("underflow")
                val = stack.pop()
                key = stack.pop()
                if not meter.charge_bytes(len(val)):
                    return Expr.Error("meter limit")
                heap[key] = val
                continue

            # ---------- STORAGE GET ----------
            if tok == b"storage_get":
                if len(stack) < 1:
                    return Expr.Error("underflow")
                key = stack.pop()
                val = self._local_get(key) or b""
                if not meter.charge_bytes(1):
                    return Expr.Error("meter limit")
                stack.append(val)
                continue

            # ---------- STORAGE SET ----------
            if tok == b"storage_set":
                if len(stack) < 2:
                    return Expr.Error("underflow")
                val = stack.pop()
                key = stack.pop()
                if not meter.charge_bytes(len(val)):
                    return Expr.Error("meter limit")
                self._local_set(key, val)
                continue

            # if no opcode matched above, treat token as literal

            # not an opcode → literal blob
            stack.append(tok)

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
