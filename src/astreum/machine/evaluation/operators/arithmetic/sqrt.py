from math import sqrt
from typing import List

from astreum.machine.models.expression import Expr, NIL, FLOAT_TAGS, _expr_to_fp64, link, str_, symbol
from astreum.machine.models.op_error import OpError


def handle_stack_sqrt(machine, stack: List[Expr], env) -> None:
    a = stack.pop()

    if a._tag in FLOAT_TAGS:
        try:
            decoded = _expr_to_fp64(a)
            computed = sqrt(decoded)
            # Unary ops stay at same precision (no overflow risk)
            from astreum.machine.models.expression.expr import _ENCODE_FUNCS
            if a._tag == "fp64":
                result = Expr("fp64", value=computed)
            else:
                result = Expr(a._tag, value=_ENCODE_FUNCS[a._tag](computed))
        except ValueError:
            raise OpError("square root of negative number")
    else:
        raise OpError(f"square root of {a._tag.lower()}")

    machine.meter.charge_bytes(result.size())
    stack.append(result)


def handle_stack_sqrt_with_result(machine, stack, env):
    try:
        handle_stack_sqrt(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
