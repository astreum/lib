from typing import List

from astreum.machine.models.expression import Expr, bytes_


def handle_stack_id(machine, stack: List[Expr]) -> None:
    expr = stack.pop()
    h = expr.hash()
    machine.meter.charge_bytes(len(h))
    stack.append(bytes_(h))
