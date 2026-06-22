from typing import List

from astreum.machine.models.expression import Expr, NIL
from astreum.machine.models.op_error import OpError


def handle_stack_tail(machine, stack: List[Expr]) -> None:
    pair = stack.pop()
    if not isinstance(pair, Expr.Link):
        raise OpError(f"tail of {type(pair).__name__.lower()}")
    if pair.tail is None:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
    else:
        machine.meter.charge_bytes(1)
        stack.append(pair.tail)
