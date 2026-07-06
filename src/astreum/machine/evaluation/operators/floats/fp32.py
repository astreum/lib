from struct import unpack
from typing import List

from astreum.machine.models.expression import Expr, fp32_, FLOAT_TAGS
from astreum.machine.models.op_error import OpError


def handle_stack_fp32(machine, stack: List[Expr]) -> None:
    """Convert value to fp32 (32-bit IEEE 754 float).
    
    Input types:
    - bytes (4 bytes): struct.unpack
    - str/symbol: parse as float then encode
    - int: convert to float then encode
    - fp32: passthrough
    - other float types: error (strict)
    """
    v = stack.pop()
    
    if v._tag == "bytes":
        if len(v.value) != 4:
            raise OpError("fp32 requires 4-byte input")
        decoded = unpack('<f', v.value)[0]
        result = fp32_(decoded)
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif v._tag in ("str", "symbol"):
        try:
            result = fp32_(float(v.value))
        except (ValueError, OverflowError):
            raise OpError("fp32: invalid literal")
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif v._tag == "int":
        try:
            result = fp32_(float(v.value))
        except OverflowError:
            raise OpError("fp32: overflow")
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif v._tag == "fp32":
        machine.meter.charge_bytes(v.size())
        stack.append(v)
    else:
        raise OpError(f"fp32 of {v._tag}")
