from typing import List

from astreum.machine.models.expression import Expr, int_, float_
from astreum.machine.models.op_error import OpError


def handle_stack_add(machine, stack: List[Expr]) -> None:
    b = stack.pop()
    a = stack.pop()

    if a._tag == "int" and b._tag == "int":
        result = int_(a.value + b.value)
    elif a._tag == "float" and b._tag == "float":
        result = float_(a.value + b.value)
    else:
        raise OpError(
            f"addition of {a._tag} and {b._tag}"
        )

    machine.meter.charge_bytes(result.size())
    stack.append(result)
