from typing import List

from astreum.expression import Expr, link, symbol, str_
from astreum.machine import OpError


def handle_stack_rot(machine, stack: List[Expr], env) -> None:
    if len(stack) < 3:
        raise OpError("stack underflow")

    c = stack.pop()
    b = stack.pop()
    a = stack.pop()

    machine.meter.charge_bytes(3)
    stack.append(b)
    stack.append(c)
    stack.append(a)


def handle_stack_rot_with_result(machine, stack, env):
    try:
        handle_stack_rot(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
