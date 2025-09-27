from typing import Dict, List, Union
from src.astreum._lispeum import Expr, Meter

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

            # if no opcode matched above, treat token as literal
            # not an opcode → literal blob
            stack.append(tok)
