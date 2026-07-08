from typing import TYPE_CHECKING, List

from astreum.machine.models.expression import Expr, NIL, link, symbol

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def handle_stack_none(
    machine: "Machine", stack: List[Expr], env
) -> None:
    machine.meter.charge_bytes(2)
    stack.append(link(NIL, symbol("none")))
