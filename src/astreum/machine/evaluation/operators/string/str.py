from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_str(machine, stack: List[Expr]) -> None:
    v = stack.pop()
    if isinstance(v, Expr.Bytes):
        try:
            val = v.value.decode("utf-8")
        except UnicodeDecodeError:
            machine.meter.charge_bytes(1)
            stack.append(NIL)
            return
        result = Expr.String(val)
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif isinstance(v, Expr.Int):
        result = Expr.String(str(v.value))
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif isinstance(v, Expr.Float):
        result = Expr.String(str(v.value))
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif isinstance(v, Expr.String):
        machine.meter.charge_bytes(v.size())
        stack.append(v)
    elif isinstance(v, Expr.Symbol):
        result = Expr.String(v.value)
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    else:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
