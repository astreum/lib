from math import sqrt
from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_sqrt(machine, stack: List[Expr]) -> None:
    a = stack.pop()

    if isinstance(a, Expr.Float):
        try:
            result = Expr.Float(sqrt(a.value))
        except ValueError:
            machine.meter.charge_bytes(1)
            stack.append(NIL)
            return
    else:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return

    machine.meter.charge_bytes(result.size())
    stack.append(result)
