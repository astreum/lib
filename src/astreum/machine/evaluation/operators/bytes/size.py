from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_size(machine, stack: List[Expr]) -> None:
    value = stack.pop()

    if not isinstance(value, Expr.Bytes):
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return

    result = Expr.Int(len(value.value))
    machine.meter.charge_bytes(result.size())
    stack.append(result)
