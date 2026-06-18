from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_abs(machine, stack: List[Expr]) -> None:
    if not stack:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return

    v = stack.pop()

    if isinstance(v, Expr.Int):
        result = Expr.Int(abs(v.value))
    elif isinstance(v, Expr.Float):
        result = Expr.Float(abs(v.value))
    else:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return

    machine.meter.charge_bytes(result.size())
    stack.append(result)
