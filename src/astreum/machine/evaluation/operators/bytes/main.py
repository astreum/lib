from struct import pack
from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_bytes(machine, stack: List[Expr]) -> None:
    v = stack.pop()
    if isinstance(v, Expr.Int):
        result = Expr.Bytes(v._encoded())
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif isinstance(v, Expr.Float):
        result = Expr.Bytes(pack("<d", v.value))
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif isinstance(v, (Expr.String, Expr.Symbol)):
        result = Expr.Bytes(v.value.encode("utf-8"))
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif isinstance(v, Expr.Bytes):
        machine.meter.charge_bytes(v.size())
        stack.append(v)
    else:
        raise OpError(f"bytes of {type(v).__name__.lower()}")
