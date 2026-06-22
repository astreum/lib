from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_mod(machine, stack: List[Expr]) -> None:
    b = stack.pop()
    a = stack.pop()

    if isinstance(a, Expr.Int) and isinstance(b, Expr.Int):
        try:
            result = Expr.Int(a.value % b.value)
        except ZeroDivisionError:
            raise OpError("modulo by zero")
    else:
        raise OpError(
            f"modulo of {type(a).__name__.lower()} and {type(b).__name__.lower()}"
        )

    machine.meter.charge_bytes(result.size())
    stack.append(result)
