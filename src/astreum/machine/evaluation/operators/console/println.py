import sys
from typing import List

from astreum.machine.models.expression import Expr, NIL, link, str_, symbol
from astreum.machine.models.op_error import OpError


def handle_stack_println(machine, stack: List[Expr], env) -> None:
    if machine.mode == "deterministic":
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return
    if not stack:
        sys.stdout.write("\n")
        sys.stdout.flush()
        stack.append(NIL)
        return
    val = stack.pop()
    sys.stdout.write(repr(val) + "\n")
    sys.stdout.flush()
    stack.append(NIL)


def handle_stack_println_with_result(machine, stack, env):
    try:
        handle_stack_println(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
