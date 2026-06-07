from typing import List

from astreum.machine.models.expression import Expr


def handle_stack_link(machine, stack: List[Expr]) -> None:
    tail = stack.pop()
    head = stack.pop()
    machine.meter.charge_bytes(1)
    stack.append(Expr.Link(head, tail))
