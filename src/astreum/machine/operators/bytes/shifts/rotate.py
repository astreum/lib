from typing import List

from astreum.expression import Expr, NIL, bytes_, get_expr_tag, int_, link, str_, symbol
from astreum.machine import OpError


def _rotate_width(to_shift, tag) -> int:
    if tag == "bytes":
        return len(to_shift.value) * 8
    bl = to_shift.value.bit_length()
    return max(((bl + 7) // 8) * 8, 8)


def handle_stack_rotate(machine, stack: List[Expr], env) -> None:
    shifts = stack.pop()
    to_shift = stack.pop()
    to_shift_tag = get_expr_tag(to_shift)
    shifts_tag = get_expr_tag(shifts)

    if to_shift_tag not in ("bytes", "int") or shifts_tag != "int":
        raise OpError(
            f"rotate of {to_shift_tag.lower()} by {shifts_tag.lower()}"
        )

    if shifts.value == 0:
        machine.meter.charge_bytes(to_shift.size())
        stack.append(to_shift)
        return

    width = _rotate_width(to_shift, to_shift_tag)
    n = abs(shifts.value) % width
    mask = (1 << width) - 1

    if to_shift_tag == "bytes":
        val = int.from_bytes(to_shift.value, "little")
    else:
        val = to_shift.value & mask

    if shifts.value > 0:
        result = ((val << n) | (val >> (width - n))) & mask
    else:
        result = ((val >> n) | (val << (width - n))) & mask

    if to_shift_tag == "bytes":
        w = len(to_shift.value)
        machine.meter.charge_bytes(w)
        stack.append(bytes_(result.to_bytes(w, "little")))
    else:
        if result & (1 << (width - 1)):
            result = result - (1 << width)
        machine.meter.charge_bytes(to_shift.size())
        stack.append(int_(result))


def handle_stack_rotate_with_result(machine, stack, env):
    try:
        handle_stack_rotate(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
