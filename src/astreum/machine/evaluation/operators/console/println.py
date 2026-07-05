import sys
from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_println(machine, stack: List[Expr]) -> None:
    if machine.mode == "deterministic":
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return
    if not stack:
        sys.stdout.write("\n")
        sys.stdout.flush()
        stack.append(NIL)
        return
    val = stack.pop()
    sys.stdout.write(repr(val) + "\n")
    sys.stdout.flush()
    stack.append(NIL)
