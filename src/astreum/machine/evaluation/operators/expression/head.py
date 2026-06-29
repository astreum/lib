from typing import List

from astreum.machine.models.expression import Expr, NIL
from astreum.machine.models.op_error import OpError


def handle_stack_head(machine, stack: List[Expr]) -> None:
    pair = stack.pop()
    if pair._tag != "link":
        raise OpError(f"head of {pair._tag}")
    if pair._head is None:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
    else:
        machine.meter.charge_bytes(1)
        stack.append(pair._head)
