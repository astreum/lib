from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_rol(machine, stack: List[Expr]) -> None:
    shifts = stack.pop()
    to_shift = stack.pop()

    for v in (to_shift, shifts):
        if not isinstance(v, Expr.Bytes):
            stack.append(NIL)
            return

    bit_width = len(to_shift.value) * 8
    mask = (1 << bit_width) - 1
    to_shift_int = int.from_bytes(to_shift.value, "little")
    shifts_int = int.from_bytes(shifts.value, "little")

    if machine.meter.enabled:
        machine.meter.charge_bytes(len(to_shift.value) + shifts_int)

    n = shifts_int % bit_width
    rotated = ((to_shift_int << n) | (to_shift_int >> (bit_width - n))) & mask
    result_bytes = rotated.to_bytes(len(to_shift.value), "little")
    stack.append(Expr.Bytes(result_bytes))
