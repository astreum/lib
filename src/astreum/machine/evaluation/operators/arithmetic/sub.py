from typing import List

from astreum.machine.models.expression import Expr, int_, NIL, FLOAT_TAGS, _expr_to_fp64, _float_result, link, str_, symbol
from astreum.machine.models.op_error import OpError


def handle_stack_sub(machine, stack: List[Expr], env) -> None:
    b = stack.pop()
    a = stack.pop()

    if a._tag == "int" and b._tag == "int":
        result = int_(a.value - b.value)
    elif a._tag in FLOAT_TAGS and b._tag in FLOAT_TAGS:
        if a._tag != b._tag:
            raise OpError(f"subtraction of {a._tag} and {b._tag}")
        # Same type: decode to fp64, compute, promote to next precision
        a_decoded = _expr_to_fp64(a)
        b_decoded = _expr_to_fp64(b)
        computed = a_decoded - b_decoded
        result = _float_result(a._tag, computed)
    else:
        raise OpError(
            f"subtraction of {a._tag} and {b._tag}"
        )

    machine.meter.charge_bytes(result.size())
    stack.append(result)


def handle_stack_sub_with_result(machine, stack, env):
    try:
        handle_stack_sub(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
