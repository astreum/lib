from math import sqrt
from typing import List

from astreum.expression import Expr, NIL, get_expr_tag, FLOAT_TAGS, _expr_to_fp64, link, str_, symbol, TYPE_SYMBOLS, FP64_SYMBOL
from astreum.machine import OpError


def handle_stack_sqrt(machine, stack: List[Expr], env) -> None:
    a = stack.pop()

    tag = get_expr_tag(a)
    if tag in FLOAT_TAGS:
        try:
            decoded = _expr_to_fp64(a)
            computed = sqrt(decoded)
        except ValueError:
            raise OpError("square root of negative number")
        from astreum.expression.expr import _ENCODE_FUNCS
        try:
            if tag == "fp64":
                _ENCODE_FUNCS["fp64"](computed)
                result = Expr("link", value=computed, tail=FP64_SYMBOL)
            else:
                result = Expr("link", value=_ENCODE_FUNCS[tag](computed), tail=TYPE_SYMBOLS[tag])
        except ValueError as e:
            raise OpError(str(e))
    else:
        raise OpError(f"square root of {tag.lower()}")

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
