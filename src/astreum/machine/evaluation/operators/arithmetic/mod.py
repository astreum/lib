from typing import List

from astreum.machine.models.expression import Expr, int_
from astreum.machine.models.op_error import OpError


def handle_stack_mod(machine, stack: List[Expr]) -> None:
    b = stack.pop()
    a = stack.pop()

    if a._tag == "int" and b._tag == "int":
        try:
            result = int_(a.value % b.value)
        except ZeroDivisionError:
            raise OpError("modulo by zero")
    else:
        raise OpError(
            f"modulo of {a._tag.lower()} and {b._tag.lower()}"
        )

    machine.meter.charge_bytes(result.size())
    stack.append(result)
