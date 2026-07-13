from typing import List

from astreum.expression import Expr, NIL, get_expr_tag, get_int_from_expr, int_, FLOAT_TAGS, _expr_to_fp64, link, str_, symbol, TYPE_SYMBOLS, FP64_SYMBOL
from astreum.machine import OpError


def handle_stack_abs(machine, stack: List[Expr], env) -> None:
    v = stack.pop()
    tag = get_expr_tag(v)

    if tag == "int":
        result = int_(abs(get_int_from_expr(v)))
    elif tag in FLOAT_TAGS:
        # Unary ops stay at same precision (no overflow risk)
        decoded = _expr_to_fp64(v)
        computed = abs(decoded)
        # Re-encode to same type
        from astreum.expression.expr import _ENCODE_FUNCS
        if tag == "fp64":
            result = Expr("link", value=computed, tail=FP64_SYMBOL)
        else:
            result = Expr("link", value=_ENCODE_FUNCS[tag](computed), tail=TYPE_SYMBOLS[tag])
    else:
        raise OpError(f"absolute value of {tag.lower()}")

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
