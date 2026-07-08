from typing import List

from astreum.machine.models.expression import Expr, link, symbol, str_
from astreum.machine.models.op_error import OpError


def handle_stack_dup(machine, stack: List[Expr], env) -> None:
    if not stack:
        raise OpError("stack underflow")
    v = stack.pop()
    machine.meter.charge_bytes(v.size())
    stack.append(v)
    stack.append(v)


def handle_stack_dup_with_result(machine, stack, env):
    try:
        handle_stack_dup(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
