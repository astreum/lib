from typing import List

from astreum.machine.models.expression import Expr, bytes_


def handle_stack_is_atom(machine, stack: List[Expr]) -> None:
    expr = stack.pop()
    machine.meter.charge_bytes(1)
    result = not expr._tag == "link"
    stack.append(bytes_(b"\x01" if result else b"\x00"))
