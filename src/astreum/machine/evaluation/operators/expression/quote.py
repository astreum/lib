from typing import List

from astreum.machine.models.expression import Expr


def handle_stack_quote(machine, stack: List[Expr]) -> None:
    v = stack.pop()
    machine.meter.charge_bytes(v.size())
    stack.append(Expr.Link(Expr.Symbol("'"), v))
