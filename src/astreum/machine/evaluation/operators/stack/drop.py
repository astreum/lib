from typing import List

from astreum.machine.models.expression import Expr, NIL, link, str_, symbol
from astreum.machine.models.op_error import OpError


def handle_stack_drop(machine, stack: List[Expr], env) -> None:
    if not stack:
        raise OpError("stack underflow")
    stack.pop()
    machine.meter.charge_bytes(1)


def handle_stack_drop_with_result(machine, stack, env):
    try:
        handle_stack_drop(machine, stack, env)
        stack.append(link(NIL, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
