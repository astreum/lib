from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def _rotate_width(to_shift) -> int:
    if isinstance(to_shift, Expr.Bytes):
        return len(to_shift.value) * 8
    bl = to_shift.value.bit_length()
    return max(((bl + 7) // 8) * 8, 8)


def handle_stack_rotate(machine, stack: List[Expr]) -> None:
    shifts = stack.pop()
    to_shift = stack.pop()

    if not isinstance(to_shift, (Expr.Bytes, Expr.Int)) or not isinstance(shifts, Expr.Int):
        raise OpError(
            f"rotate of {type(to_shift).__name__.lower()} by {type(shifts).__name__.lower()}"
        )

    if shifts.value == 0:
        machine.meter.charge_bytes(to_shift.size())
        stack.append(to_shift)
        return

    width = _rotate_width(to_shift)
    n = abs(shifts.value) % width
    mask = (1 << width) - 1

    if isinstance(to_shift, Expr.Bytes):
        val = int.from_bytes(to_shift.value, "little")
    else:
        val = to_shift.value & mask

    if shifts.value > 0:
        result = ((val << n) | (val >> (width - n))) & mask
    else:
        result = ((val >> n) | (val << (width - n))) & mask

    if isinstance(to_shift, Expr.Bytes):
        w = len(to_shift.value)
        machine.meter.charge_bytes(w)
        stack.append(Expr.Bytes(result.to_bytes(w, "little")))
    else:
        if result & (1 << (width - 1)):
            result = result - (1 << width)
        machine.meter.charge_bytes(to_shift.size())
        stack.append(Expr.Int(result))
