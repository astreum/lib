from typing import TYPE_CHECKING, List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def _evaluation(machine, expr, stack, env):
    from astreum.machine.evaluation.main import evaluation
    return evaluation(machine, expr, stack, env)


def handle_stack_dip(
    machine: "Machine", stack: List[Expr], env
) -> List[Expr]:
    if len(stack) < 2:
        raise OpError("stack underflow")
    expr = stack.pop()
    value = stack.pop()
    machine.meter.charge_bytes(expr.size())
    stack = _evaluation(machine, expr, stack, env)
    stack.append(value)
    return stack
