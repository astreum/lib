from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_mul(machine, stack: List[Expr]) -> None:
    b = stack.pop()
    a = stack.pop()

    if isinstance(a, Expr.Int) and isinstance(b, Expr.Int):
        result = Expr.Int(a.value * b.value)
    elif isinstance(a, Expr.Float) and isinstance(b, Expr.Float):
        result = Expr.Float(a.value * b.value)
    else:
        raise OpError(
            f"multiplication of {type(a).__name__.lower()} and {type(b).__name__.lower()}"
        )

    machine.meter.charge_bytes(result.size())
    stack.append(result)
