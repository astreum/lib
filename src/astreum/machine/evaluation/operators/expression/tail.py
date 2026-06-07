from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_tail(machine, stack: List[Expr]) -> None:
    pair = stack.pop()
    machine.meter.charge_bytes(1)
    if isinstance(pair, Expr.Link):
        if pair.tail is None:
            machine.meter.charge_bytes(1)
            stack.append(NIL)
        else:
            stack.append(pair.tail)
    else:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
