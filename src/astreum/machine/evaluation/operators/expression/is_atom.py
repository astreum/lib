from typing import List

from src.astreum.machine.models.expression import Expr


def handle_stack_is_atom(machine, stack: List[Expr]) -> None:
    expr = stack.pop()
    machine.meter.charge_bytes(1)
    result = not isinstance(expr, Expr.Link)
    stack.append(Expr.Bytes(b"\x01" if result else b"\x00"))
