from struct import unpack
from typing import List

from astreum.machine.models.expression import Expr, e4m3_, FLOAT_TAGS, _expr_to_fp64
from astreum.machine.models.op_error import OpError


def handle_stack_e4m3(machine, stack: List[Expr]) -> None:
    """Convert value to e4m3 (8-bit float with 4-bit exponent, 3-bit mantissa).
    
    Input types:
    - bytes (1 byte): decode via LUT
    - str/symbol: parse as float then encode
    - int: convert to float then encode
    - e4m3: passthrough
    - other float types: error (strict)
    """
    v = stack.pop()
    
    if v._tag == "bytes":
        if len(v.value) != 1:
            raise OpError("e4m3 requires 1-byte input")
        # Decode via LUT, re-encode to ensure canonical form
        from astreum.machine.models.expression.expr import _E4M3_TABLE
        decoded = _E4M3_TABLE[v.value[0]]
        result = e4m3_(decoded)
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif v._tag in ("str", "symbol"):
        try:
            result = e4m3_(float(v.value))
        except (ValueError, OverflowError):
            raise OpError("e4m3: invalid literal")
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif v._tag == "int":
        try:
            result = e4m3_(float(v.value))
        except OverflowError:
            raise OpError("e4m3: overflow")
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif v._tag == "e4m3":
        machine.meter.charge_bytes(v.size())
        stack.append(v)
    else:
        raise OpError(f"e4m3 of {v._tag}")
