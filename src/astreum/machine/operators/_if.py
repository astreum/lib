from typing import TYPE_CHECKING, List

from astreum.machine.environment import Env
from astreum.expression import Expr, NIL, FLOAT_TAGS, _expr_to_fp64, link, str_, symbol
from astreum.machine import OpError

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def _evaluation(machine, expr, stack, env):
    """Lazy import to break circular dependency."""
    from astreum.machine.evaluator import evaluation
    return evaluation(machine, expr, stack, env)


def is_truthy(expr: Expr) -> bool:
    if expr._tag == "bytes":
        return int.from_bytes(expr.value, "big") != 0
    if expr._tag == "int":
        return expr.value != 0
    if expr._tag in FLOAT_TAGS:
        return _expr_to_fp64(expr) != 0.0
    if expr._tag == "link":
        if (
            expr._tail is not None
            and expr._tail._tag == "symbol"
        ):
            tag = expr._tail.value
            if tag == "err":
                return False
            return True
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


def handle_stack_if_with_result(machine, stack, env):
    try:
        stack = handle_stack_if(machine, stack, env)
        top = stack.pop()
        stack.append(link(top, symbol("ok")))
        return stack
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
        return stack
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
        return stack
