from typing import TYPE_CHECKING, List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def _evaluation(machine, expr, stack, env):
    from astreum.machine.evaluation.main import evaluation
    return evaluation(machine, expr, stack, env)


def handle_stack_match(
    machine: "Machine", stack: List[Expr], env
) -> List[Expr]:
    if len(stack) < 4:
        raise OpError("stack underflow")
    fail_cl = stack.pop()
    succ_cl = stack.pop()
    succ_tag = stack.pop()
    val = stack.pop()

    if (
        val._tag == "link"
        and val._tail is not None
        and val._tail._tag == "symbol"
        and val._tail.value == succ_tag.value
    ):
        stack.append(val._head)
        return _evaluation(machine, succ_cl, stack, env)
    else:
        stack.append(val)
        return _evaluation(machine, fail_cl, stack, env)
