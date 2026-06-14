from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_symbol(machine, stack: List[Expr]) -> None:
    v = stack.pop()
    if isinstance(v, Expr.Bytes):
        try:
            name = v.value.decode("utf-8")
        except UnicodeDecodeError:
            machine.meter.charge_bytes(1)
            stack.append(NIL)
            return
        machine.meter.charge_bytes(v.size())
        stack.append(Expr.Symbol(name))
    else:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
