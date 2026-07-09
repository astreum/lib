from typing import List

from astreum.expression import Expr, NIL, link, str_, symbol
from astreum.machine import OpError


def handle_stack_link(machine, stack: List[Expr], env) -> None:
    tail = stack.pop()
    head = stack.pop()
    machine.meter.charge_bytes(1)
    stack.append(link(head, tail))


def handle_stack_link_with_result(machine, stack, env):
    try:
        handle_stack_link(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
