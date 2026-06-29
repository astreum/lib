from typing import List

from astreum.machine.models.expression import Expr, bytes_
from astreum.machine.models.op_error import OpError


def handle_stack_or(machine, stack: List[Expr]) -> None:
    b = stack.pop()
    a = stack.pop()

    for v in (a, b):
        if v._tag != "bytes":
            raise OpError(
                f"bitwise or of {a._tag.lower()} and {b._tag.lower()}"
            )

    if machine.meter.enabled:
        max_byte_width = max(len(a.value), len(b.value))
        machine.meter.charge_bytes(max_byte_width)

    a_int = int.from_bytes(a.value, "little")
    b_int = int.from_bytes(b.value, "little")
    result_bytes = (a_int | b_int).to_bytes((a_int | b_int).bit_length() or 1, "little")
    stack.append(bytes_(result_bytes))
