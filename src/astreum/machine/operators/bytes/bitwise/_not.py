from typing import List

from astreum.expression import Expr, NIL, bytes_, link, str_, symbol
from astreum.machine import OpError


def handle_stack_not(machine, stack: List[Expr], env) -> None:
    a = stack.pop()

    if a._tag != "bytes":
        raise OpError(f"bitwise not of {a._tag.lower()}")

    # Charge: 2 bytes per byte of operand
    machine.meter.charge_bytes(len(a.value) * 2)

    w = max(len(a.value), 1)
    mask = (1 << (w * 8)) - 1
    au = int.from_bytes(a.value, "little", signed=False)
    result_bytes = (~au & mask).to_bytes(w, "little", signed=False)
    stack.append(bytes_(result_bytes))


def handle_stack_not_with_result(machine, stack, env):
    try:
        handle_stack_not(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
