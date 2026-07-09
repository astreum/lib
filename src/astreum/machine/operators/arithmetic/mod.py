from typing import List

from astreum.expression import Expr, NIL, int_, link, str_, symbol
from astreum.machine import OpError


def handle_stack_mod(machine, stack: List[Expr], env) -> None:
    b = stack.pop()
    a = stack.pop()

    if a._tag == "int" and b._tag == "int":
        try:
            result = int_(a.value % b.value)
        except ZeroDivisionError:
            raise OpError("modulo by zero")
    else:
        raise OpError(
            f"modulo of {a._tag.lower()} and {b._tag.lower()}"
        )

    machine.meter.charge_bytes(result.size())
    stack.append(result)


def handle_stack_mod_with_result(machine, stack, env):
    try:
        handle_stack_mod(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
