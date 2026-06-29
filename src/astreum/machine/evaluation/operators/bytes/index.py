from typing import List

from astreum.machine.models.expression import Expr, bytes_
from astreum.machine.models.op_error import OpError


def handle_stack_index(machine, stack: List[Expr]) -> None:
    index = stack.pop()
    value = stack.pop()

    if value._tag != "bytes" or index._tag != "int":
        raise OpError(
            f"index of {value._tag} by {index._tag}"
        )

    if index.value < 0 or index.value >= len(value.value):
        raise OpError(
            f"index {index.value} out of bounds for bytes of length {len(value.value)}"
        )

    machine.meter.charge_bytes(1)
    stack.append(bytes_(value.value[index.value:index.value + 1]))
