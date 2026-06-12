from typing import List

from astreum.machine.models.expression import Expr


def handle_stack_swap(machine, stack: List[Expr]) -> None:
    b = stack.pop()
    a = stack.pop()
    machine.meter.charge_bytes(1)
    stack.append(b)
    stack.append(a)
