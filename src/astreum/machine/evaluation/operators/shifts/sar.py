from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_sar(machine, stack: List[Expr]) -> None:
    shifts = stack.pop()
    to_shift = stack.pop()

    for v in (to_shift, shifts):
        if not isinstance(v, Expr.Bytes):
            stack.append(NIL)
            return

    # Arithmetic right shift: preserves the sign bit (MSB of the original
    # width). If the sign bit was 1, shifted-out positions fill with 1s;
    # if 0, they fill with 0s (same as logical).
    w = max(len(to_shift.value), 1)
    orig_bits = w * 8
    to_shift_int = int.from_bytes(to_shift.value, "little")
    shifts_int = int.from_bytes(shifts.value, "little")

    if machine.meter.enabled:
        machine.meter.charge_bytes(len(to_shift.value) + shifts_int)

    sign_bit = (to_shift_int >> (orig_bits - 1)) & 1
    if shifts_int >= orig_bits:
        shifted = (1 << orig_bits) - 1 if sign_bit else 0
    else:
        shifted = to_shift_int >> shifts_int
        if sign_bit:
            fill = ((1 << shifts_int) - 1) << (orig_bits - shifts_int)
            shifted |= fill

    result_bytes = shifted.to_bytes(w, "little")
    stack.append(Expr.Bytes(result_bytes))
