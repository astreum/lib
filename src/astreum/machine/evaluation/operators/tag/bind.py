from typing import TYPE_CHECKING, List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def _evaluation(machine, expr, stack, env):
    from astreum.machine.evaluation.main import evaluation
    return evaluation(machine, expr, stack, env)


def handle_stack_bind(
    machine: "Machine", stack: List[Expr], env
) -> List[Expr]:
    if len(stack) < 4:
        raise OpError("stack underflow")

    closure = stack.pop()
    failure_tag = stack.pop()
    success_tag = stack.pop()
    tagged = stack.pop()

    if success_tag._tag != "symbol":
        raise OpError("bind success tag must be a symbol")
    if failure_tag._tag != "symbol":
        raise OpError("bind failure tag must be a symbol")
    if tagged._tag != "link" or tagged._tail is None or tagged._tail._tag != "symbol":
        raise OpError("bind of non-tagged value")

    st = success_tag.value
    ft = failure_tag.value
    actual_tag = tagged._tail.value

    if actual_tag == st:
        stack.append(tagged._head)
        return _evaluation(machine, closure, stack, env)
    elif actual_tag == ft:
        stack.append(tagged)
        return stack
    else:
        raise OpError(f"bind of unknown tag: {actual_tag}")
