from struct import pack
from typing import List

from astreum.machine.models.expression import Expr, bytes_
from astreum.machine.models.expression.expr import _encode_int
from astreum.machine.models.op_error import OpError


def handle_stack_bytes(machine, stack: List[Expr]) -> None:
    v = stack.pop()
    if v._tag == "int":
        result = bytes_(_encode_int(v._value))
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif v._tag == "float":
        result = bytes_(pack("<d", v.value))
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif v._tag in ("str", "symbol"):
        result = bytes_(v.value.encode("utf-8"))
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif v._tag == "bytes":
        machine.meter.charge_bytes(v.size())
        stack.append(v)
    else:
        raise OpError(f"bytes of {v._tag}")
