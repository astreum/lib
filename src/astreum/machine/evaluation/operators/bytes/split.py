from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_split(machine, stack: List[Expr]) -> None:
    index = stack.pop()
    value = stack.pop()

    if not isinstance(value, Expr.Bytes) or not isinstance(index, Expr.Int):
        raise OpError(
            f"split of {type(value).__name__.lower()} at {type(index).__name__.lower()}"
        )

    if index.value < 0 or index.value > len(value.value):
        raise OpError(
            f"split index {index.value} out of bounds for bytes of length {len(value.value)}"
        )

    left = Expr.Bytes(value.value[:index.value])
    right = Expr.Bytes(value.value[index.value:])
    machine.meter.charge_bytes(left.size() + right.size())
    stack.append(Expr.Link(left, right))
