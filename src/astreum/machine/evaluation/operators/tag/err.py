from typing import TYPE_CHECKING, List

from astreum.machine.models.expression import Expr, link, symbol
from astreum.machine.models.op_error import OpError

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def handle_stack_err(machine: "Machine", stack: List[Expr], env) -> None:
    if not stack:
        raise OpError("stack underflow")
    msg = stack.pop()
    machine.meter.charge_bytes(msg.size() + 1)
    stack.append(link(msg, symbol("err")))
