from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_size(machine, stack: List[Expr]) -> None:
    value = stack.pop()

    if not isinstance(value, Expr.Bytes):
        raise OpError(f"size of {type(value).__name__.lower()}")

    result = Expr.Int(len(value.value))
    machine.meter.charge_bytes(result.size())
    stack.append(result)
