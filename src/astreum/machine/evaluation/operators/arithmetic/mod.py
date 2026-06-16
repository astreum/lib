from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_mod(machine, stack: List[Expr]) -> None:
    b = stack.pop()
    a = stack.pop()

    if isinstance(a, Expr.Int) and isinstance(b, Expr.Int):
        try:
            result = Expr.Int(a.value % b.value)
        except ZeroDivisionError:
            machine.meter.charge_bytes(1)
            stack.append(NIL)
            return
    else:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return

    machine.meter.charge_bytes(result.size())
    stack.append(result)
