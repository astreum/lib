from typing import TYPE_CHECKING, List

from astreum.machine.models.environment import Env
from astreum.machine.models.expression import Expr, NIL, link, str_, symbol
from astreum.machine.models.op_error import OpError

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def _evaluation(machine, expr, stack, env):
    """Lazy import to break circular dependency."""
    from astreum.machine.evaluation.main import evaluation
    return evaluation(machine, expr, stack, env)


def handle_stack_box(
    machine: "Machine", stack: List[Expr], env: Env
) -> None:
    if not stack:
        raise OpError("stack underflow")
    body = stack.pop()
    if not stack:
        raise OpError("stack underflow")
    params = stack.pop()

    if params._tag != "link":
        raise OpError(f"box of {params._tag}")

    param_list = []
    p = params
    while p._tag == "link" and p._head is not None:
        param_list.append(p._head.value)
        if p._tail is None or p._tail is NIL:
            break
        p = p._tail
    num_args = len(param_list)
    args = []
    for _ in range(num_args):
        if not stack:
            raise OpError("stack underflow")
        args.append(stack.pop())
    args.reverse()

    cost = params.size() + sum(a.size() for a in args)
    machine.meter.charge_bytes(cost)

    fn_env_data = dict(zip(param_list, args))
    fn_env = Env(data=fn_env_data)
    fn_stack = []
    result_stack = _evaluation(machine, body, fn_stack, fn_env)
    if result_stack:
        result = result_stack.pop()
        stack.append(result)


def handle_stack_box_with_result(machine, stack, env):
    try:
        handle_stack_box(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
