import sys
from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_print(machine, stack: List[Expr]) -> None:
    if machine.mode == "deterministic":
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return
    if not stack:
        stack.append(NIL)
        return
    val = stack.pop()
    sys.stdout.write(repr(val))
    sys.stdout.flush()
    stack.append(NIL)
