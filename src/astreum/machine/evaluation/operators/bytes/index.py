from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_index(machine, stack: List[Expr]) -> None:
    index = stack.pop()
    value = stack.pop()

    if not isinstance(value, Expr.Bytes) or not isinstance(index, Expr.Int):
        raise OpError(
            f"index of {type(value).__name__.lower()} by {type(index).__name__.lower()}"
        )

    if index.value < 0 or index.value >= len(value.value):
        raise OpError(
            f"index {index.value} out of bounds for bytes of length {len(value.value)}"
        )

    machine.meter.charge_bytes(1)
    stack.append(Expr.Bytes(value.value[index.value:index.value + 1]))
