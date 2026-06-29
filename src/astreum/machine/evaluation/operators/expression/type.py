from typing import List

from astreum.machine.models.expression import Expr, symbol
from astreum.machine.models.op_error import OpError


def handle_stack_type(machine, stack: List[Expr]) -> None:
    if not stack:
        raise OpError("stack underflow")
    expr = stack.pop()
    stack.append(symbol(expr._tag))
