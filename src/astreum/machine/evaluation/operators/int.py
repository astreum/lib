from typing import List

from astreum.machine.models.expression import Expr, int_
from astreum.machine.models.op_error import OpError


def handle_stack_int(machine, stack: List[Expr]) -> None:
    v = stack.pop()
    if v._tag == "bytes":
        result = int_(int.from_bytes(v.value, "little", signed=True))
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif v._tag in ("str", "symbol"):
        try:
            result = int_(int(v.value))
        except ValueError:
            raise OpError("int: invalid literal")
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif v._tag == "float":
        try:
            result = int_(int(v.value))
        except (ValueError, OverflowError):
            raise OpError("int: overflow")
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif v._tag == "int":
        machine.meter.charge_bytes(v.size())
        stack.append(v)
    else:
        raise OpError(f"int of {v._tag}")
