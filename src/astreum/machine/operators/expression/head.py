from typing import List

from astreum.expression import Expr, NIL, link, str_, symbol
from astreum.machine import OpError


def handle_stack_head(machine, stack: List[Expr], env) -> None:
    pair = stack.pop()
    if pair._tag != "link":
        raise OpError(f"head of {pair._tag}")
    if pair._head is None:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
    else:
        machine.meter.charge_bytes(1)
        stack.append(pair._head)


def handle_stack_head_with_result(machine, stack, env):
    try:
        handle_stack_head(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
