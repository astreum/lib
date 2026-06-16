from typing import List

from astreum.machine.models.expression import Expr, NIL


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
            machine.meter.charge_bytes(1)
            stack.append(NIL)
            return
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif isinstance(v, Expr.Float):
        try:
            result = Expr.Int(int(v.value))
        except (ValueError, OverflowError):
            machine.meter.charge_bytes(1)
            stack.append(NIL)
            return
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif isinstance(v, Expr.Int):
        machine.meter.charge_bytes(v.size())
        stack.append(v)
    else:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
