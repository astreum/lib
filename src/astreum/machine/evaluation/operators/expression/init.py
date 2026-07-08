from typing import List

from astreum.machine.models.expression import Expr, NIL, link, str_, symbol
from astreum.machine.models.op_error import OpError


def handle_stack_init(machine, stack: List[Expr], env) -> None:
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


def handle_stack_init_with_result(machine, stack, env):
    try:
        handle_stack_init(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
