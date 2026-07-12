from typing import List

from astreum.expression import Expr, NIL, bytes_, get_expr_tag, link, str_, symbol
from astreum.machine import OpError


def handle_stack_or(machine, stack: List[Expr], env) -> None:
    b = stack.pop()
    a = stack.pop()
    a_tag = get_expr_tag(a)
    b_tag = get_expr_tag(b)

    for tag in (a_tag, b_tag):
        if tag != "bytes":
            raise OpError(
                f"bitwise or of {a_tag.lower()} and {b_tag.lower()}"
            )

    max_byte_width = max(len(a.value), len(b.value))
    machine.meter.charge_bytes(max_byte_width)

    a_int = int.from_bytes(a.value, "little")
    b_int = int.from_bytes(b.value, "little")
    result_bytes = (a_int | b_int).to_bytes((a_int | b_int).bit_length() or 1, "little")
    stack.append(bytes_(result_bytes))


def handle_stack_or_with_result(machine, stack, env):
    try:
        handle_stack_or(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
