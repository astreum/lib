from typing import List

from astreum.machine.models.expression import Expr, NIL, link, str_, symbol
from astreum.machine.models.op_error import OpError


def handle_stack_type(machine, stack: List[Expr], env) -> None:
    if not stack:
        raise OpError("stack underflow")
    expr = stack.pop()
    stack.append(symbol(expr._tag))


def handle_stack_type_with_result(machine, stack, env):
    try:
        handle_stack_type(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
