from struct import pack
from typing import List

from astreum.machine.models.expression import Expr, bytes_, FLOAT_TAGS, _float_to_bytes
from astreum.machine.models.expression.expr import _encode_int
from astreum.machine.models.op_error import OpError


def handle_stack_bytes(machine, stack: List[Expr]) -> None:
    v = stack.pop()
    if v._tag == "int":
        result = bytes_(_encode_int(v._value))
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif v._tag in FLOAT_TAGS:
        # Encode float to its wire bytes representation
        result = bytes_(_float_to_bytes(v._tag, v._value))
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
