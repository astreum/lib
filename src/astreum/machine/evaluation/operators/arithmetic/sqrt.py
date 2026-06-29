from math import sqrt
from typing import List

from astreum.machine.models.expression import Expr, float_
from astreum.machine.models.op_error import OpError


def handle_stack_sqrt(machine, stack: List[Expr]) -> None:
    a = stack.pop()

    if a._tag == "float":
        try:
            result = float_(sqrt(a.value))
        except ValueError:
            raise OpError("square root of negative number")
    else:
        raise OpError(f"square root of {a._tag.lower()}")

    machine.meter.charge_bytes(result.size())
    stack.append(result)
