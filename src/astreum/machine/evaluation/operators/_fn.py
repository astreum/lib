from typing import TYPE_CHECKING, List

from astreum.machine.models.environment import Env
from astreum.machine.models.expression import Expr

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def _evaluation(machine, expr, stack, env):
    """Lazy import to break circular dependency."""
    from astreum.machine.evaluation.main import evaluation
    return evaluation(machine, expr, stack, env)


def handle_stack_fn(
    machine: "Machine", stack: List[Expr], env: Env
) -> None:
    body = stack.pop()
    params = stack.pop()
    param_list = []
    p = params
    while isinstance(p, Expr.Link) and p.head is not None and isinstance(p, Expr.Link):
        param_list.append(p.head.value)
        if not isinstance(p.tail, Expr.Link):
            # Last param is p.tail itself (not wrapped in a Link)
            if p.tail is not None and hasattr(p.tail, 'value'):
                param_list.append(p.tail.value)
            break
        p = p.tail
    num_args = len(param_list)
    args = []
    for _ in range(num_args):
        args.append(stack.pop())
    args.reverse()

    # Charge: param symbols + arg values (def-per-binding model)
    cost = params.size() + sum(a.size() for a in args)
    machine.meter.charge_bytes(cost)

    fn_env_data = dict(zip(param_list, args))
    fn_env = Env(data=fn_env_data, parent=env, def_target=machine.global_env)
    fn_stack = []
    result_stack = _evaluation(machine, body, fn_stack, fn_env)
    if result_stack:
        result = result_stack.pop()
        stack.append(result)
