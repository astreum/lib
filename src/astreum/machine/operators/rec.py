from typing import TYPE_CHECKING, List

from astreum.machine.environment import Env
from astreum.expression import Expr, NIL, link, str_, symbol
from astreum.machine import OpError
from astreum.machine.operators._if import is_truthy

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def _evaluation(machine, expr, stack, env):
    """Lazy import to break circular dependency."""
    from astreum.machine.evaluator import evaluation

    return evaluation(machine, expr, stack, env)


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
        condition = current_stack.pop()
        machine.meter.charge_bytes(condition.size())

        if is_truthy(condition):
            machine.meter.charge_bytes(then_branch.size())
            current_stack = _evaluation(machine, then_branch, current_stack, env)
            return current_stack

        machine.meter.charge_bytes(rec1.size())
        current_stack = _evaluation(machine, rec1, current_stack, env)
        current_stack = recurse(current_stack)
        machine.meter.charge_bytes(rec2.size())
        current_stack = _evaluation(machine, rec2, current_stack, env)
        return current_stack

    return recurse(stack)


def handle_stack_rec_with_result(machine, stack, env):
    try:
        stack = handle_stack_rec(machine, stack, env)
        top = stack.pop()
        stack.append(link(top, symbol("ok")))
        return stack
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
        return stack
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
        return stack
