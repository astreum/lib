from struct import unpack
from typing import List

from astreum.machine.models.expression import Expr, fp64_, FLOAT_TAGS
from astreum.machine.models.op_error import OpError


def handle_stack_fp64(machine, stack: List[Expr]) -> None:
    """Convert value to fp64 (64-bit IEEE 754 float).
    
    Input types:
    - bytes (8 bytes): struct.unpack
    - str/symbol: parse as float then encode
    - int: convert to float then encode
    - fp64: passthrough
    - other float types: error (strict)
    """
    v = stack.pop()
    
    if v._tag == "bytes":
        if len(v.value) != 8:
            raise OpError("fp64 requires 8-byte input")
        decoded = unpack("<d", v.value)[0]
        result = fp64_(decoded)
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif v._tag in ("str", "symbol"):
        try:
            result = fp64_(float(v.value))
        except (ValueError, OverflowError):
            raise OpError("fp64: invalid literal")
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif v._tag == "int":
        try:
            result = fp64_(float(v.value))
        except OverflowError:
            raise OpError("fp64: overflow")
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif v._tag == "fp64":
        machine.meter.charge_bytes(v.size())
        stack.append(v)
    else:
        raise OpError(f"fp64 of {v._tag}")
