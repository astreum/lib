from typing import List

from src.astreum.machine.models.expression import Expr, NIL


def handle_stack_head(machine, stack: List[Expr]) -> None:
    pair = stack.pop()
    machine.meter.charge_bytes(1)
    if isinstance(pair, Expr.Link):
        if pair.head is None:
            machine.meter.charge_bytes(1)
            stack.append(NIL)
        else:
            stack.append(pair.head)
    else:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
