from struct import pack, unpack
from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_fmul(machine, stack: List[Expr]) -> None:
    b = stack.pop()
    a = stack.pop()

    for v in (a, b):
        if not isinstance(v, Expr.Bytes):
            stack.append(NIL)
            return
        size = len(v.value)
        if size not in (4, 8):
            stack.append(NIL)
            return

    width = max(len(a.value), len(b.value))

    if machine.meter.enabled:
        if width == 8:
            # double: 11-bit exp (2 bytes) + 52-bit mant (7 bytes)
            cost = 2 + 7 * 7
        else:
            # float: 8-bit exp (1 byte) + 23-bit mant (3 bytes)
            cost = 1 + 3 * 3
        machine.meter.charge_bytes(cost)

    if width == 8:
        f_a = unpack("<d", a.value)[0]
        f_b = unpack("<d", b.value)[0]
        result_bytes = pack("<d", f_a * f_b)
    else:
        f_a = unpack("<f", a.value)[0]
        f_b = unpack("<f", b.value)[0]
        result_bytes = pack("<f", f_a * f_b)

    stack.append(Expr.Bytes(result_bytes))
