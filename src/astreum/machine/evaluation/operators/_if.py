from typing import TYPE_CHECKING, List

from astreum.machine.models.environment import Env
from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def _evaluation(machine, expr, stack, env):
    """Lazy import to break circular dependency."""
    from astreum.machine.evaluation.main import evaluation
    return evaluation(machine, expr, stack, env)


def is_truthy(expr: Expr) -> bool:
    if expr._tag == "bytes":
        return int.from_bytes(expr.value, "big") != 0
    if expr._tag == "int":
        return expr.value != 0
    if expr._tag == "float":
        return expr.value != 0.0
    if expr._tag == "link":
        if (
            expr._head is not None
            and expr._head._tag == "symbol"
            and expr._head.value == "err"
        ):
            return False
        return expr._head is not None
    return True


def handle_stack_if(
    machine: "Machine", stack: List[Expr], env: Env
) -> List[Expr]:
    if len(stack) < 3:
        raise OpError("stack underflow")
    else_branch = stack.pop()
    then_branch = stack.pop()
    cond_quote = stack.pop()
    _evaluation(machine, cond_quote, stack, env)
    if not stack:
        raise OpError("stack underflow")
    condition = stack.pop()
    machine.meter.charge_bytes(condition.size())
    branch = then_branch if is_truthy(condition) else else_branch
    return _evaluation(machine, branch, stack, env)
