from typing import List

from astreum.machine.models.expression import Expr, int_
from astreum.machine.models.op_error import OpError


def handle_stack_size(machine, stack: List[Expr]) -> None:
    value = stack.pop()

    if value._tag != "bytes":
        raise OpError(f"size of {value._tag}")

    result = int_(len(value.value))
    machine.meter.charge_bytes(result.size())
    stack.append(result)
