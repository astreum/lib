from math import sqrt
from struct import pack, unpack
from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_fsqrt(machine, stack: List[Expr]) -> None:
    a = stack.pop()

    if not isinstance(a, Expr.Bytes):
        stack.append(NIL)
        return

    size = len(a.value)
    if size not in (4, 8):
        stack.append(NIL)
        return

    if machine.meter.enabled:
        machine.meter.charge_bytes(size * size)

    if size == 8:
        f = unpack("<d", a.value)[0]
        result_bytes = pack("<d", sqrt(f))
    else:
        f = unpack("<f", a.value)[0]
        result_bytes = pack("<f", sqrt(f))

    stack.append(Expr.Bytes(result_bytes))
