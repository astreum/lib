from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_nand(machine, stack: List[Expr]) -> None:
    b = stack.pop()
    if not isinstance(b, Expr.Bytes):
        stack.append(NIL)
        return

    a = stack.pop()
    if not isinstance(a, Expr.Bytes):
        stack.append(NIL)
        return

    w = max(len(a.value), len(b.value), 1)

    if machine.meter.enabled:
        machine.meter.charge_bytes(w * 2)

    au = int.from_bytes(a.value.rjust(w, b"\x00"), "little", signed=False)
    bu = int.from_bytes(b.value.rjust(w, b"\x00"), "little", signed=False)
    mask = (1 << (w * 8)) - 1
    result_bytes = (~(au & bu) & mask).to_bytes(w, "little", signed=False)
    stack.append(Expr.Bytes(result_bytes))
