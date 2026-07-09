from typing import List

from astreum.expression import Expr, NIL, int_, FLOAT_TAGS, _expr_to_fp64, link, str_, symbol
from astreum.machine import OpError


def handle_stack_abs(machine, stack: List[Expr], env) -> None:
    v = stack.pop()

    if v._tag == "int":
        result = int_(abs(v.value))
    elif v._tag in FLOAT_TAGS:
        # Unary ops stay at same precision (no overflow risk)
        decoded = _expr_to_fp64(v)
        computed = abs(decoded)
        # Re-encode to same type
        from astreum.expression.expr import _ENCODE_FUNCS
        if v._tag == "fp64":
            result = Expr("fp64", value=computed)
        else:
            result = Expr(v._tag, value=_ENCODE_FUNCS[v._tag](computed))
    else:
        raise OpError(f"absolute value of {v._tag.lower()}")

    machine.meter.charge_bytes(result.size())
    stack.append(result)


def handle_stack_abs_with_result(machine, stack, env):
    try:
        handle_stack_abs(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
