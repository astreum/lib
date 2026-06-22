from struct import unpack
from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_float(machine, stack: List[Expr]) -> None:
    v = stack.pop()
    if isinstance(v, Expr.Bytes):
        if len(v.value) != 8:
            raise OpError("float requires 8-byte input")
        result = Expr.Float(unpack("<d", v.value)[0])
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif isinstance(v, (Expr.String, Expr.Symbol)):
        try:
            result = Expr.Float(float(v.value))
        except (ValueError, OverflowError):
            raise OpError("float: invalid literal")
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif isinstance(v, Expr.Int):
        try:
            result = Expr.Float(float(v.value))
        except OverflowError:
            raise OpError("float: overflow")
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif isinstance(v, Expr.Float):
        machine.meter.charge_bytes(v.size())
        stack.append(v)
    else:
        raise OpError(f"float of {type(v).__name__.lower()}")
