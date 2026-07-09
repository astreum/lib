import sys
from typing import List

from astreum.expression import Expr, NIL, link, str_, symbol
from astreum.machine import OpError


def handle_stack_print(machine, stack: List[Expr], env) -> None:
    if machine.mode == "deterministic":
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return
    if not stack:
        stack.append(NIL)
        return
    val = stack.pop()
    sys.stdout.write(repr(val))
    sys.stdout.flush()
    stack.append(NIL)


def handle_stack_print_with_result(machine, stack, env):
    try:
        handle_stack_print(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
