from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_sub(machine, stack: List[Expr]) -> None:
    b = stack.pop()
    a = stack.pop()

    if isinstance(a, Expr.Int) and isinstance(b, Expr.Int):
        result = Expr.Int(a.value - b.value)
    elif isinstance(a, Expr.Float) and isinstance(b, Expr.Float):
        result = Expr.Float(a.value - b.value)
    elif isinstance(a, Expr.Float) and isinstance(b, Expr.Int):
        try:
            b_f = float(b.value)
        except OverflowError:
            machine.meter.charge_bytes(1)
            stack.append(NIL)
            return
        result = Expr.Float(a.value - b_f)
    elif isinstance(a, Expr.Int) and isinstance(b, Expr.Float):
        try:
            a_f = float(a.value)
        except OverflowError:
            machine.meter.charge_bytes(1)
            stack.append(NIL)
            return
        result = Expr.Float(a_f - b.value)
    else:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return

    machine.meter.charge_bytes(result.size())
    stack.append(result)
