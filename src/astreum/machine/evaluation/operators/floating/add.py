from struct import pack, unpack
from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_fadd(machine, stack: List[Expr]) -> None:
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

    if machine.meter.enabled:
        machine.meter.charge_bytes(max(len(a.value), len(b.value)))

    if len(a.value) == 8:
        f_a = unpack("<d", a.value)[0]
    else:
        f_a = unpack("<f", a.value)[0]

    if len(b.value) == 8:
        f_b = unpack("<d", b.value)[0]
    else:
        f_b = unpack("<f", b.value)[0]

    result_width = max(len(a.value), len(b.value))
    if result_width == 8:
        result_bytes = pack("<d", f_a + f_b)
    else:
        result_bytes = pack("<f", f_a + f_b)

    stack.append(Expr.Bytes(result_bytes))
