from typing import List

from astreum.expression import Expr, NIL, bytes_, int_, link, str_, symbol
from astreum.machine import OpError


def handle_stack_shift(machine, stack: List[Expr], env) -> None:
    shifts = stack.pop()
    to_shift = stack.pop()

    if to_shift._tag not in ("bytes", "int") or shifts._tag != "int":
        raise OpError(
            f"shift of {to_shift._tag.lower()} by {shifts._tag.lower()}"
        )

    if shifts.value == 0:
        machine.meter.charge_bytes(to_shift.size())
        stack.append(to_shift)
        return

    if to_shift._tag == "bytes":
        w = len(to_shift.value)
        val = int.from_bytes(to_shift.value, "little")
        mask = (1 << (w * 8)) - 1
        if shifts.value > 0:
            result = (val << shifts.value) & mask
        else:
            result = val >> abs(shifts.value)
        machine.meter.charge_bytes(w)
        stack.append(bytes_(result.to_bytes(w, "little")))
    else:
        if shifts.value > 0:
            result = to_shift.value << shifts.value
        else:
            result = to_shift.value >> abs(shifts.value)
        machine.meter.charge_bytes(to_shift.size())
        stack.append(int_(result))


def handle_stack_shift_with_result(machine, stack, env):
    try:
        handle_stack_shift(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
