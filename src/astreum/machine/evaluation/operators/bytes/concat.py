from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_concat(machine, stack: List[Expr]) -> None:
    b = stack.pop()
    a = stack.pop()

    if not isinstance(a, Expr.Bytes) or not isinstance(b, Expr.Bytes):
        raise OpError(
            f"concatenation of {type(a).__name__.lower()} and {type(b).__name__.lower()}"
        )

    result = Expr.Bytes(a.value + b.value)
    machine.meter.charge_bytes(result.size())
    stack.append(result)
