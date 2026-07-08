from typing import List

from astreum.machine.models.expression import Expr, NIL, bytes_, link, str_, symbol
from astreum.machine.models.op_error import OpError


def handle_stack_xor(machine, stack: List[Expr], env) -> None:
    b = stack.pop()
    a = stack.pop()

    for v in (a, b):
        if v._tag != "bytes":
            raise OpError(
                f"bitwise xor of {a._tag.lower()} and {b._tag.lower()}"
            )

    max_byte_width = max(len(a.value), len(b.value))
    machine.meter.charge_bytes(max_byte_width)

    a_int = int.from_bytes(a.value, "little")
    b_int = int.from_bytes(b.value, "little")
    result_bytes = (a_int ^ b_int).to_bytes((a_int ^ b_int).bit_length() or 1, "little")
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
