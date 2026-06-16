from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_index(machine, stack: List[Expr]) -> None:
    index = stack.pop()
    value = stack.pop()

    if not isinstance(value, Expr.Bytes) or not isinstance(index, Expr.Int):
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return

    if index.value < 0 or index.value >= len(value.value):
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return

    machine.meter.charge_bytes(1)
    stack.append(Expr.Bytes(value.value[index.value:index.value + 1]))
