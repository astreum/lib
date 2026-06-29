from typing import List

from astreum.machine.models.expression import Expr, symbol
from astreum.machine.models.op_error import OpError


def handle_stack_init(machine, stack: List[Expr]) -> None:
    if len(stack) < 2:
        raise OpError("stack underflow")
    tag_expr = stack.pop()
    value_expr = stack.pop()

    if tag_expr._tag != "symbol":
        raise OpError(f"init requires a symbol tag, got {tag_expr._tag}")

    tag = tag_expr.value

    if value_expr._tag == tag:
        stack.append(value_expr)
    else:
        stack.append(Expr(tag, value=value_expr))
