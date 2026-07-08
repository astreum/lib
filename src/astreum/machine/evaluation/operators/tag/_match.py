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
    """Match a tagged value against an expected tag and branch accordingly.

    Pops four values from the stack, in order: a failure closure, a success
    closure, an expected tag, and the value to match. If ``val`` is a
    ``link`` expression whose tail is a ``symbol`` matching ``succ_tag``,
    the link's head is pushed onto the stack and the success closure is
    evaluated. Otherwise, the original value is pushed back and the failure
    closure is evaluated.

    Args:
        machine: The machine instance used to continue evaluation.
        stack: The current evaluation stack; must contain at least four
            expressions: [..., val, succ_tag, succ_cl, fail_cl] (top to
            bottom: fail_cl, succ_cl, succ_tag, val).
        env: The environment in which the resulting closure is evaluated.

    Returns:
        The updated stack after evaluating the appropriate closure
        (success or failure).

    Raises:
        OpError: If the stack has fewer than four elements.
    """
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
