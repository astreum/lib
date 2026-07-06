from struct import unpack
from typing import List

from astreum.machine.models.expression import Expr, fp16_, FLOAT_TAGS
from astreum.machine.models.op_error import OpError


def handle_stack_fp16(machine, stack: List[Expr]) -> None:
    """Convert value to fp16 (16-bit IEEE 754 float).
    
    Input types:
    - bytes (2 bytes): struct.unpack
    - str/symbol: parse as float then encode
    - int: convert to float then encode
    - fp16: passthrough
    - other float types: error (strict)
    """
    v = stack.pop()
    
    if v._tag == "bytes":
        if len(v.value) != 2:
            raise OpError("fp16 requires 2-byte input")
        decoded = unpack('<e', v.value)[0]
        result = fp16_(decoded)
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif v._tag in ("str", "symbol"):
        try:
            result = fp16_(float(v.value))
        except (ValueError, OverflowError):
            raise OpError("fp16: invalid literal")
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif v._tag == "int":
        try:
            result = fp16_(float(v.value))
        except OverflowError:
            raise OpError("fp16: overflow")
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif v._tag == "fp16":
        machine.meter.charge_bytes(v.size())
        stack.append(v)
    else:
        raise OpError(f"fp16 of {v._tag}")
