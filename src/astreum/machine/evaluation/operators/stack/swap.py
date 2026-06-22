from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_swap(machine, stack: List[Expr]) -> None:
    if len(stack) < 2:
        raise OpError("stack underflow")
    b = stack.pop()
    a = stack.pop()
    machine.meter.charge_bytes(1)
    stack.append(b)
    stack.append(a)
