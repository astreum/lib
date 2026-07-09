from typing import List

from astreum.expression import Expr, NIL, bytes_, link, str_, symbol
from astreum.machine import OpError


def handle_stack_id(machine, stack: List[Expr], env) -> None:
    expr = stack.pop()
    h = expr.hash()
    machine.meter.charge_bytes(len(h))
    stack.append(bytes_(h))


def handle_stack_id_with_result(machine, stack, env):
    try:
        handle_stack_id(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
