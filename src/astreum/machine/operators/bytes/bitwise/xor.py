from typing import List

from astreum.expression import Expr, NIL, bytes_, get_expr_tag, link, str_, symbol
from astreum.machine import OpError


def handle_stack_xor(machine, stack: List[Expr], env) -> None:
    b = stack.pop()
    a = stack.pop()
    a_tag = get_expr_tag(a)
    b_tag = get_expr_tag(b)

    for tag in (a_tag, b_tag):
        if tag != "bytes":
            raise OpError(
                f"bitwise xor of {a_tag.lower()} and {b_tag.lower()}"
            )

    max_byte_width = max(len(a.value), len(b.value))
    machine.meter.charge_bytes(max_byte_width)

    a_int = int.from_bytes(a.value, "little")
    b_int = int.from_bytes(b.value, "little")
    result = a_int ^ b_int
    byte_count = max((result.bit_length() + 7) // 8, 1)
    result_bytes = result.to_bytes(byte_count, "little")
    stack.append(bytes_(result_bytes))


def handle_stack_xor_with_result(machine, stack, env):
    try:
        handle_stack_xor(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
