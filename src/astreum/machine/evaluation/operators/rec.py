from typing import TYPE_CHECKING, List

from astreum.machine.models.environment import Env
from astreum.machine.models.expression import Expr
from astreum.machine.evaluation.operators._if import is_truthy

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def _evaluation(machine, expr, stack, env):
    """Lazy import to break circular dependency."""
    from astreum.machine.evaluation.main import evaluation

    return evaluation(machine, expr, stack, env)


def handle_stack_rec(
    machine: "Machine", stack: List[Expr], env: Env
) -> List[Expr]:
    rec2 = stack.pop()
    rec1 = stack.pop()
    then_branch = stack.pop()
    pred = stack.pop()

    def recurse(current_stack: List[Expr]) -> List[Expr]:
        machine.meter.charge_bytes(pred.size())
        current_stack = _evaluation(machine, pred, current_stack, env)
        condition = current_stack.pop()
        machine.meter.charge_bytes(condition.size())

        if is_truthy(condition):
            machine.meter.charge_bytes(then_branch.size())
            return _evaluation(machine, then_branch, current_stack, env)

        machine.meter.charge_bytes(rec1.size())
        current_stack = _evaluation(machine, rec1, current_stack, env)
        current_stack = recurse(current_stack)
        machine.meter.charge_bytes(rec2.size())
        return _evaluation(machine, rec2, current_stack, env)

    return recurse(stack)
