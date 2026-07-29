from typing import List

from astreum.expression import Expr, get_expr_tag, get_int_from_expr, int_, NIL, FLOAT_TAGS, _expr_to_fp64, _float_result, link, str_, symbol
from astreum.machine import OpError


def handle_stack_add(machine, stack: List[Expr], env) -> None:
    b = stack.pop()
    a = stack.pop()

    a_tag = get_expr_tag(a)
    b_tag = get_expr_tag(b)
    if a_tag == "int" and b_tag == "int":
        result = int_(get_int_from_expr(a) + get_int_from_expr(b))
    elif a_tag in FLOAT_TAGS and b_tag in FLOAT_TAGS:
        if a_tag != b_tag:
            raise OpError(f"addition of {a_tag} and {b_tag}")
        a_decoded = _expr_to_fp64(a)
        b_decoded = _expr_to_fp64(b)
        computed = a_decoded + b_decoded
        try:
            result = _float_result(a_tag, computed)
        except ValueError as e:
            raise OpError(str(e))
    else:
        raise OpError(
            f"addition of {a_tag} and {b_tag}"
        )

    machine.meter.charge_bytes(result.size())
    stack.append(result)


def handle_stack_add_with_result(machine, stack, env):
    try:
        handle_stack_add(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
