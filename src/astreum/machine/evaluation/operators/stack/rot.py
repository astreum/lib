from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_rot(machine, stack: List[Expr]) -> None:
    if len(stack) < 3:
        raise OpError("stack underflow")

    c = stack.pop()
    b = stack.pop()
    a = stack.pop()

    machine.meter.charge_bytes(3)
    stack.append(b)
    stack.append(c)
    stack.append(a)
