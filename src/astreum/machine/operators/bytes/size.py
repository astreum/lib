from typing import List

from astreum.expression import Expr, NIL, int_, link, str_, symbol
from astreum.machine import OpError


def handle_stack_size(machine, stack: List[Expr], env) -> None:
    value = stack.pop()

    if value._tag != "bytes":
        raise OpError(f"size of {value._tag}")

    result = int_(len(value.value))
    machine.meter.charge_bytes(result.size())
    stack.append(result)


def handle_stack_size_with_result(machine, stack, env):
    try:
        handle_stack_size(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
