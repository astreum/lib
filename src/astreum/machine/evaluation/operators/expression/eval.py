from typing import TYPE_CHECKING, List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def _evaluation(machine, expr, stack, env):
    from astreum.machine.evaluation.main import evaluation
    return evaluation(machine, expr, stack, env)


def handle_stack_eval(machine, stack: List[Expr], env) -> List[Expr]:
    if not stack:
        machine.meter.charge_bytes(1)
        raise OpError("stack underflow")
    val = stack.pop()
    machine.meter.charge_bytes(val.size())
    return _evaluation(machine, val, stack, env)
