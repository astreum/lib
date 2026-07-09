from typing import List

from astreum.expression import Expr, link, symbol, str_
from astreum.machine import OpError


def handle_stack_swap(machine, stack: List[Expr], env) -> None:
    if len(stack) < 2:
        raise OpError("stack underflow")
    b = stack.pop()
    a = stack.pop()
    machine.meter.charge_bytes(1)
    stack.append(b)
    stack.append(a)


def handle_stack_swap_with_result(machine, stack, env):
    try:
        handle_stack_swap(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
