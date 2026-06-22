from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_dup(machine, stack: List[Expr]) -> None:
    if not stack:
        raise OpError("stack underflow")
    v = stack.pop()
    machine.meter.charge_bytes(v.size())
    stack.append(v)
    stack.append(v)
