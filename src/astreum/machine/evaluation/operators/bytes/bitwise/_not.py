from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_not(machine, stack: List[Expr]) -> None:
    a = stack.pop()

    if not isinstance(a, Expr.Bytes):
        raise OpError(f"bitwise not of {type(a).__name__.lower()}")

    # Charge: 2 bytes per byte of operand
    machine.meter.charge_bytes(len(a.value) * 2)

    w = max(len(a.value), 1)
    mask = (1 << (w * 8)) - 1
    au = int.from_bytes(a.value, "little", signed=False)
    result_bytes = (~au & mask).to_bytes(w, "little", signed=False)
    stack.append(Expr.Bytes(result_bytes))
