from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_shr(machine, stack: List[Expr]) -> None:
    shifts = stack.pop()
    if not isinstance(shifts, Expr.Bytes):
        stack.append(NIL)
        return

    to_shift = stack.pop()
    if not isinstance(to_shift, Expr.Bytes):
        stack.append(NIL)
        return

    to_shift_int = int.from_bytes(to_shift.value, "little")
    shifts_int = int.from_bytes(shifts.value, "little")

    if machine.meter.enabled:
        machine.meter.charge_bytes(len(to_shift.value) + shifts_int)

    result_bytes = (to_shift_int >> shifts_int).to_bytes((to_shift_int >> shifts_int).bit_length() or 1, "little")
    stack.append(Expr.Bytes(result_bytes))
