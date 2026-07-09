import sys
from typing import List

from astreum.expression import Expr, NIL, link, str_, symbol
from astreum.machine import OpError


def handle_stack_println(machine, stack: List[Expr], env) -> None:
    if not stack:
        sys.stdout.write("\n")
        sys.stdout.flush()
        return
    val = stack.pop()
    sys.stdout.write(repr(val) + "\n")
    sys.stdout.flush()


def handle_stack_println_with_result(machine, stack, env):
    try:
        handle_stack_println(machine, stack, env)
        stack.append(link(NIL, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
