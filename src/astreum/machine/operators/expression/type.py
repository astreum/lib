from typing import List

from astreum.expression import Expr, NIL, get_expr_tag, link, str_, symbol
from astreum.machine import OpError


def handle_stack_type(machine, stack: List[Expr], env) -> None:
    if not stack:
        raise OpError("stack underflow")
    expr = stack.pop()
    stack.append(symbol(get_expr_tag(expr)))


def handle_stack_type_with_result(machine, stack, env):
    try:
        handle_stack_type(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
