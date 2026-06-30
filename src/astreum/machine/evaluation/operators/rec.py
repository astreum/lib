from typing import TYPE_CHECKING, List

from astreum.machine.models.environment import Env
from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError
from astreum.machine.evaluation.operators._if import is_truthy

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def _evaluation(machine, expr, stack, env):
    """Lazy import to break circular dependency."""
    from astreum.machine.evaluation.main import evaluation

    return evaluation(machine, expr, stack, env)


def _check_err(stack: List[Expr]) -> None:
    """If top of stack is (err reason), raise OpError with that reason."""
    if stack and stack[-1]._tag == "link":
        top = stack[-1]
        if (
            top._head._tag == "str"
            and top._tail._tag == "symbol"
            and top._tail.value == "err"
        ):
            raise OpError(top._head.value)


def handle_stack_rec(
    machine: "Machine", stack: List[Expr], env: Env
) -> List[Expr]:
    if len(stack) < 4:
        raise OpError("stack underflow")

    rec2 = stack.pop()
    rec1 = stack.pop()
    then_branch = stack.pop()
    pred = stack.pop()

    def recurse(current_stack: List[Expr]) -> List[Expr]:
        machine.meter.charge_bytes(pred.size())
        current_stack = _evaluation(machine, pred, current_stack, env)
        _check_err(current_stack)
        condition = current_stack.pop()
        machine.meter.charge_bytes(condition.size())

        if is_truthy(condition):
            machine.meter.charge_bytes(then_branch.size())
            current_stack = _evaluation(machine, then_branch, current_stack, env)
            _check_err(current_stack)
            return current_stack

        machine.meter.charge_bytes(rec1.size())
        current_stack = _evaluation(machine, rec1, current_stack, env)
        _check_err(current_stack)
        current_stack = recurse(current_stack)
        _check_err(current_stack)
        machine.meter.charge_bytes(rec2.size())
        current_stack = _evaluation(machine, rec2, current_stack, env)
        _check_err(current_stack)
        return current_stack

    return recurse(stack)
