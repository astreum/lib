from typing import TYPE_CHECKING, List

from astreum.machine.models.environment import Env
from astreum.machine.models.expression import Expr, NIL, link, str_, symbol
from astreum.machine.models.op_error import OpError

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def _evaluation(machine, expr, stack, env):
    from astreum.machine.evaluation.main import evaluation
    return evaluation(machine, expr, stack, env)


def handle_stack_apply(machine: "Machine", stack: List[Expr], env) -> None:
    if not stack:
        raise OpError("stack underflow")
    closure_val = stack.pop()
    if closure_val._tag != "closure":
        raise OpError(f"apply of {closure_val._tag}")

    c = closure_val._value  # Closure
    num_args = len(c.params)
    args = []
    for _ in range(num_args):
        if not stack:
            raise OpError("stack underflow")
        args.append(stack.pop())
    args.reverse()

    cost = sum(a.size() for a in args)
    machine.meter.charge_bytes(cost)

    captured = machine.library[c.captured_env_uuid]
    apply_env = Env(data=dict(zip(c.params, args)), parent=captured)
    apply_stack = []
    result_stack = _evaluation(machine, c.body, apply_stack, apply_env)
    if result_stack:
        result = result_stack.pop()
        stack.append(result)


def handle_stack_apply_with_result(machine, stack, env):
    try:
        handle_stack_apply(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
