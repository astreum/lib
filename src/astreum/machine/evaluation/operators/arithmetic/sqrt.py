from math import sqrt
from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_sqrt(machine, stack: List[Expr]) -> None:
    a = stack.pop()

    if isinstance(a, Expr.Float):
        try:
            result = Expr.Float(sqrt(a.value))
        except ValueError:
            raise OpError("square root of negative number")
    else:
        raise OpError(f"square root of {type(a).__name__.lower()}")

    machine.meter.charge_bytes(result.size())
    stack.append(result)
