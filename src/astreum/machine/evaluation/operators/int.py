from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_int(machine, stack: List[Expr]) -> None:
    v = stack.pop()
    if isinstance(v, Expr.Bytes):
        result = Expr.Int(int.from_bytes(v.value, "little", signed=True))
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif isinstance(v, (Expr.String, Expr.Symbol)):
        try:
            result = Expr.Int(int(v.value))
        except ValueError:
            raise OpError("int: invalid literal")
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif isinstance(v, Expr.Float):
        try:
            result = Expr.Int(int(v.value))
        except (ValueError, OverflowError):
            raise OpError("int: overflow")
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif isinstance(v, Expr.Int):
        machine.meter.charge_bytes(v.size())
        stack.append(v)
    else:
        raise OpError(f"int of {type(v).__name__.lower()}")
