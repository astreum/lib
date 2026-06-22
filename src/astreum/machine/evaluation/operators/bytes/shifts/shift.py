from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_shift(machine, stack: List[Expr]) -> None:
    shifts = stack.pop()
    to_shift = stack.pop()

    if not isinstance(to_shift, (Expr.Bytes, Expr.Int)) or not isinstance(shifts, Expr.Int):
        raise OpError(
            f"shift of {type(to_shift).__name__.lower()} by {type(shifts).__name__.lower()}"
        )

    if shifts.value == 0:
        machine.meter.charge_bytes(to_shift.size())
        stack.append(to_shift)
        return

    if isinstance(to_shift, Expr.Bytes):
        w = len(to_shift.value)
        val = int.from_bytes(to_shift.value, "little")
        mask = (1 << (w * 8)) - 1
        if shifts.value > 0:
            result = (val << shifts.value) & mask
        else:
            result = val >> abs(shifts.value)
        machine.meter.charge_bytes(w)
        stack.append(Expr.Bytes(result.to_bytes(w, "little")))
    else:
        if shifts.value > 0:
            result = to_shift.value << shifts.value
        else:
            result = to_shift.value >> abs(shifts.value)
        machine.meter.charge_bytes(to_shift.size())
        stack.append(Expr.Int(result))
