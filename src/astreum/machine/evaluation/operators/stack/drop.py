from typing import List

from astreum.machine.models.expression import Expr


def handle_stack_drop(machine, stack: List[Expr]) -> None:
    stack.pop()
    machine.meter.charge_bytes(1)
