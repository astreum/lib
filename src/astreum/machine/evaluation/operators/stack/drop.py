from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_drop(machine, stack: List[Expr]) -> None:
    if not stack:
        raise OpError("stack underflow")
    stack.pop()
    machine.meter.charge_bytes(1)
