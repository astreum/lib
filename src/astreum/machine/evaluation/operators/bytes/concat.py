from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_concat(machine, stack: List[Expr]) -> None:
    b = stack.pop()
    a = stack.pop()

    if not isinstance(a, Expr.Bytes) or not isinstance(b, Expr.Bytes):
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return

    result = Expr.Bytes(a.value + b.value)
    machine.meter.charge_bytes(result.size())
    stack.append(result)
