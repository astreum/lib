from typing import List

from astreum.machine.models.expression import Expr, str_
from astreum.machine.models.op_error import OpError


def handle_stack_str(machine, stack: List[Expr]) -> None:
    v = stack.pop()
    if v._tag == "bytes":
        try:
            val = v.value.decode("utf-8")
        except UnicodeDecodeError:
            raise OpError("str: bytes are not valid UTF-8")
        result = str_(val)
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif v._tag == "int":
        result = str_(str(v.value))
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif v._tag == "float":
        result = str_(str(v.value))
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif v._tag == "str":
        machine.meter.charge_bytes(v.size())
        stack.append(v)
    elif v._tag == "symbol":
        result = str_(v.value)
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    else:
        raise OpError(f"str of {v._tag}")
