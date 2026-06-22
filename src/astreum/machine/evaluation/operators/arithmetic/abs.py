from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_abs(machine, stack: List[Expr]) -> None:
    v = stack.pop()

    if isinstance(v, Expr.Int):
        result = Expr.Int(abs(v.value))
    elif isinstance(v, Expr.Float):
        result = Expr.Float(abs(v.value))
    else:
        raise OpError(f"absolute value of {type(v).__name__.lower()}")

    machine.meter.charge_bytes(result.size())
    stack.append(result)
