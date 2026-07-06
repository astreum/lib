from struct import unpack
from typing import List

from astreum.machine.models.expression import Expr, bf16_, FLOAT_TAGS
from astreum.machine.models.op_error import OpError


def handle_stack_bf16(machine, stack: List[Expr]) -> None:
    """Convert value to bf16 (16-bit brain float).
    
    Input types:
    - bytes (2 bytes): decode via LUT
    - str/symbol: parse as float then encode
    - int: convert to float then encode
    - bf16: passthrough
    - other float types: error (strict)
    """
    v = stack.pop()
    
    if v._tag == "bytes":
        if len(v.value) != 2:
            raise OpError("bf16 requires 2-byte input")
        from astreum.machine.models.expression.expr import _unpack_u16, _BF16_TABLE
        decoded = _BF16_TABLE[_unpack_u16(v.value)[0]]
        result = bf16_(decoded)
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif v._tag in ("str", "symbol"):
        try:
            result = bf16_(float(v.value))
        except (ValueError, OverflowError):
            raise OpError("bf16: invalid literal")
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif v._tag == "int":
        try:
            result = bf16_(float(v.value))
        except OverflowError:
            raise OpError("bf16: overflow")
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif v._tag == "bf16":
        machine.meter.charge_bytes(v.size())
        stack.append(v)
    else:
        raise OpError(f"bf16 of {v._tag}")
