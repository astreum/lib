from typing import List

from astreum.expression import Expr, NIL, link, str_, symbol
from astreum.machine import OpError


def handle_stack_quote(machine, stack: List[Expr], env) -> None:
    v = stack.pop()
    machine.meter.charge_bytes(v.size())
    stack.append(link(symbol("'"), v))


def handle_stack_quote_with_result(machine, stack, env):
    try:
        handle_stack_quote(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
