from typing import List

from astreum.machine.models.expression import Expr


def handle_stack_dup(machine, stack: List[Expr]) -> None:
    v = stack.pop()
    machine.meter.charge_bytes(v.size())
    stack.append(v)
    stack.append(v)
