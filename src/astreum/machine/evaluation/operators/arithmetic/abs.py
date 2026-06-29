from typing import List

from astreum.machine.models.expression import Expr, int_, float_
from astreum.machine.models.op_error import OpError


def handle_stack_abs(machine, stack: List[Expr]) -> None:
    v = stack.pop()

    if v._tag == "int":
        result = int_(abs(v.value))
    elif v._tag == "float":
        result = float_(abs(v.value))
    else:
        raise OpError(f"absolute value of {v._tag.lower()}")

    machine.meter.charge_bytes(result.size())
    stack.append(result)
