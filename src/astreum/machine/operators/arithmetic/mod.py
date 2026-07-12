from typing import List

from astreum.expression import Expr, NIL, get_expr_tag, get_int_from_expr, int_, link, str_, symbol
from astreum.machine import OpError


def handle_stack_mod(machine, stack: List[Expr], env) -> None:
    b = stack.pop()
    a = stack.pop()

    a_tag = get_expr_tag(a)
    b_tag = get_expr_tag(b)
    if a_tag == "int" and b_tag == "int":
        try:
            result = int_(get_int_from_expr(a) % get_int_from_expr(b))
        except ZeroDivisionError:
            raise OpError("modulo by zero")
    else:
        raise OpError(
            f"modulo of {a_tag.lower()} and {b_tag.lower()}"
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
