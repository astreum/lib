from struct import unpack
from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_float(machine, stack: List[Expr]) -> None:
    v = stack.pop()
    if isinstance(v, Expr.Bytes):
        if len(v.value) != 8:
            machine.meter.charge_bytes(1)
            stack.append(NIL)
            return
        result = Expr.Float(unpack("<d", v.value)[0])
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif isinstance(v, (Expr.String, Expr.Symbol)):
        try:
            result = Expr.Float(float(v.value))
        except (ValueError, OverflowError):
            machine.meter.charge_bytes(1)
            stack.append(NIL)
            return
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif isinstance(v, Expr.Int):
        try:
            result = Expr.Float(float(v.value))
        except OverflowError:
            machine.meter.charge_bytes(1)
            stack.append(NIL)
            return
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif isinstance(v, Expr.Float):
        machine.meter.charge_bytes(v.size())
        stack.append(v)
    else:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
