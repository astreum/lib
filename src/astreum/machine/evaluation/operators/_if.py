from typing import TYPE_CHECKING, List

from astreum.machine.models.environment import Env
from astreum.machine.models.expression import Expr

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def _evaluation(machine, expr, stack, env):
    """Lazy import to break circular dependency."""
    from astreum.machine.evaluation.main import evaluation
    return evaluation(machine, expr, stack, env)


def is_truthy(expr: Expr) -> bool:
    if isinstance(expr, Expr.Bytes):
        return int.from_bytes(expr.value, "big") != 0
    if isinstance(expr, Expr.Link):
        return expr.head is not None


def handle_stack_if(
    machine: "Machine", stack: List[Expr], env: Env
) -> List[Expr]:
    else_branch = stack.pop()
    then_branch = stack.pop()
    condition = stack.pop()
    machine.meter.charge_bytes(condition.size())
    branch = then_branch if is_truthy(condition) else else_branch
    return _evaluation(machine, branch, stack, env)
