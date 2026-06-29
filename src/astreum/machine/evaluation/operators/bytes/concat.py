from typing import List

from astreum.machine.models.expression import Expr, bytes_
from astreum.machine.models.op_error import OpError


def handle_stack_concat(machine, stack: List[Expr]) -> None:
    b = stack.pop()
    a = stack.pop()

    if a._tag != "bytes" or b._tag != "bytes":
        raise OpError(
            f"concatenation of {a._tag} and {b._tag}"
        )

    result = bytes_(a.value + b.value)
    machine.meter.charge_bytes(result.size())
    stack.append(result)
