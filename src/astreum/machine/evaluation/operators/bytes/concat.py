from typing import List

from astreum.machine.models.expression import Expr, NIL, bytes_, link, str_, symbol
from astreum.machine.models.op_error import OpError


def handle_stack_concat(machine, stack: List[Expr], env) -> None:
    b = stack.pop()
    a = stack.pop()

    if a._tag != "bytes" or b._tag != "bytes":
        raise OpError(
            f"concatenation of {a._tag} and {b._tag}"
        )

    result = bytes_(a.value + b.value)
    machine.meter.charge_bytes(result.size())
    stack.append(result)


def handle_stack_concat_with_result(machine, stack, env):
    try:
        handle_stack_concat(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
