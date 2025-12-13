from typing import Dict, List, Union

from astreum.storage.models.atom import ZERO32, Atom, AtomKind
from ..models.expression import Expr, error_expr
from ..models.meter import Meter

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
    """Bitwise NAND (NOT-AND) on two byte strings, zero-extending to max width.

    The NAND gate yields 0 only when all inputs are 1; otherwise it outputs 1.
    Truth table:
        A | B | NAND
        0 | 0 |  1
        0 | 1 |  1
        1 | 0 |  1
        1 | 1 |  0
    """
    w = max(len(a), len(b), 1)
    au = int.from_bytes(a.rjust(w, b"\x00"), "big", signed=False)
    bu = int.from_bytes(b.rjust(w, b"\x00"), "big", signed=False)
    mask = (1 << (w * 8)) - 1
    resu = (~(au & bu)) & mask
    return resu.to_bytes(w, "big", signed=False)

def low_eval(self, code: List[bytes], meter: Meter) -> Expr:
        """Execute low-level bytecode with stack/heap semantics under metering."""
        heap: Dict[bytes, bytes] = {}

        stack: List[bytes] = []
        pc = 0

        while True:
            if pc >= len(code):
                if len(stack) != 1:
                    return error_expr("low_eval", "bad stack")
                # wrap successful result as an Expr.Bytes
                return Expr.Bytes(stack.pop())

            tok = code[pc]
            pc += 1

            # ---------- ADD ----------
            # if tok == b"add":
            #     if len(stack) < 2:
            #         return error_expr("low_eval", "underflow")
            #     b_b = stack.pop()
            #     a_b = stack.pop()
            #     a_i = tc_to_int(a_b)
            #     b_i = tc_to_int(b_b)
            #     res_i = a_i + b_i
            #     width = max(len(a_b), len(b_b), min_tc_width(res_i))
            #     res_b = int_to_tc(res_i, width)
            #     # charge for both operands' byte widths
            #     if not meter.charge_bytes(len(a_b) + len(b_b)):
            #         return error_expr("low_eval", "meter limit")
            #     stack.append(res_b)
            #     continue

            # ---------- NAND ----------
            
            if tok == b"nand":
                if len(stack) < 2:
                    return error_expr("low_eval", "underflow")
                b_b = stack.pop()
                a_b = stack.pop()
                res_b = nand_bytes(a_b, b_b)
                # bitwise cost: 2 * max(len(a), len(b))
                if not meter.charge_bytes(2 * max(len(a_b), len(b_b), 1)):
                    return error_expr("low_eval", "meter limit")
                stack.append(res_b)
                continue

            # ---------- JUMP ----------
            if tok == b"jump":
                if len(stack) < 1:
                    return error_expr("low_eval", "underflow")
                tgt_b = stack.pop()
                if not meter.charge_bytes(1):
                    return error_expr("low_eval", "meter limit")
                tgt_i = tc_to_int(tgt_b)
                if tgt_i < 0 or tgt_i >= len(code):
                    return error_expr("low_eval", "bad jump")
                pc = tgt_i
                continue

            # ---------- HEAP GET ----------
            if tok == b"heap_get":
                if len(stack) < 1:
                    return error_expr("low_eval", "underflow")
                key = stack.pop()
                val = heap.get(key) or b""
                # get cost: 1
                if not meter.charge_bytes(1):
                    return error_expr("low_eval", "meter limit")
                stack.append(val)
                continue

            # ---------- HEAP SET ----------
            if tok == b"heap_set":
                if len(stack) < 2:
                    return error_expr("low_eval", "underflow")
                val = stack.pop()
                key = stack.pop()
                if not meter.charge_bytes(len(val)):
                    return error_expr("low_eval", "meter limit")
                heap[key] = val
                continue

            # ---------- ATOM SLICE ----------
            if tok == b"atom_slice":
                if len(stack) < 3:
                    return error_expr("low_eval", "underflow")
                len_b = stack.pop()
                idx_b = stack.pop()
                id_b = stack.pop()

                idx = tc_to_int(idx_b)
                length = tc_to_int(len_b)
                if idx < 0 or length < 0:
                    return error_expr("low_eval", "bad slice")

                atom = self.storage_get(key=id_b)
                if atom is None:
                    return error_expr("low_eval", "unknown atom")

                data = atom.data
                slice_bytes = data[idx : idx + length]

                if not meter.charge_bytes(len(slice_bytes)):
                    return error_expr("low_eval", "meter limit")

                new_atom = Atom(data=slice_bytes, kind=atom.kind)
                new_id = new_atom.object_id()
                try:
                    self._hot_storage_set(key=new_id, value=new_atom)
                except RuntimeError:
                    return error_expr("low_eval", "storage error")

                stack.append(new_id)
                continue

            # ---------- ATOM LINK ----------
            if tok == b"atom_link":
                if len(stack) < 2:
                    return error_expr("low_eval", "underflow")
                id2_b = stack.pop()
                id1_b = stack.pop()

                if not meter.charge_bytes(len(id1_b) + len(id2_b)):
                    return error_expr("low_eval", "meter limit")
                
                atom = self.storage_get(key=id_b)
                if atom is None:
                    return error_expr("low_eval", "unknown atom")

                new_atom = Atom(data=id1_b, next_id=id2_b, kind=atom.kind)
                new_id = new_atom.object_id()

                try:
                    self._hot_storage_set(key=new_id, value=new_atom)
                except RuntimeError:
                    return error_expr("low_eval", "storage error")

                stack.append(new_id)
                continue

            # ---------- ATOM CONCAT ----------
            if tok == b"atom_concat":
                if len(stack) < 2:
                    return error_expr("low_eval", "underflow")
                id2_b = stack.pop()
                id1_b = stack.pop()

                atom1 = self.storage_get(key=id1_b)
                atom2 = self.storage_get(key=id2_b)
                if atom1 is None or atom2 is None:
                    return error_expr("low_eval", "unknown atom")

                joined = atom1.data + atom2.data

                if not meter.charge_bytes(len(joined)):
                    return error_expr("low_eval", "meter limit")

                new_atom = Atom(data=joined, kind=AtomKind.BYTES)
                new_id = new_atom.object_id()

                try:
                    self._hot_storage_set(key=new_id, value=new_atom)
                except RuntimeError:
                    return error_expr("low_eval", "storage error")

                stack.append(new_id)
                continue

                        # ---------- ATOM NEW ----------
            
            if tok == b"atom_new":
                if len(stack) < 2:
                    return error_expr("low_eval", "underflow")
                data_b = stack.pop()
                kind_b = stack.pop()

                if len(kind_b) != 1:
                    return error_expr("low_eval", "bad atom kind")

                kind_value = kind_b[0]
                try:
                    kind = AtomKind(kind_value)
                except ValueError:
                    return error_expr("low_eval", "unknown atom kind")

                if not meter.charge_bytes(len(data_b)):
                    return error_expr("low_eval", "meter limit")

                new_atom = Atom(data=data_b, kind=kind)
                new_id = new_atom.object_id()

                try:
                    self._hot_storage_set(key=new_id, value=new_atom)
                except RuntimeError:
                    return error_expr("low_eval", "storage error")

                stack.append(new_id)
                continue

                        # ---------- ATOM LOAD ----------
            
            if tok == b"atom_load":
                if len(stack) < 3:
                    return error_expr("low_eval", "underflow")
                len_b = stack.pop()
                idx_b = stack.pop()
                id_b = stack.pop()

                idx = tc_to_int(idx_b)
                length = tc_to_int(len_b)
                if idx < 0 or length < 0:
                    return error_expr("low_eval", "bad load")
                if length > 32:
                    return error_expr("low_eval", "load too wide")

                atom = self.storage_get(key=id_b)
                if atom is None:
                    return error_expr("low_eval", "unknown atom")

                data = atom.data
                chunk = data[idx : idx + length]

                if not meter.charge_bytes(len(chunk)):
                    return error_expr("low_eval", "meter limit")

                stack.append(chunk)
                continue

            # if no opcode matched above, treat token as literal
            # not an opcode → literal blob
            stack.append(tok)
