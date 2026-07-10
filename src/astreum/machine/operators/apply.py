import uuid
from typing import TYPE_CHECKING, List

from astreum.machine.environment import Env
from astreum.expression import Expr, NIL, link, str_, symbol
from astreum.machine import OpError

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def _evaluation(machine, expr, stack, env):
    from astreum.machine.evaluator import evaluation
    return evaluation(machine, expr, stack, env)


def handle_stack_apply(machine: "Machine", stack: List[Expr], env) -> None:
    if not stack:
        raise OpError("stack underflow")
    fn_val = stack.pop()

    if fn_val._tag != "link" or fn_val._tail is None or fn_val._tail._tag != "symbol":
        raise OpError(f"apply of {fn_val._tag}")

    inner = fn_val._head
    body = inner._head
    params = inner._tail
    tag = fn_val._tail.value

    if tag == "lambda":
        env_uuid_bytes = body._head._value
        body = body._tail
        parent = machine.library[uuid.UUID(bytes=env_uuid_bytes)]
    elif tag == "fn":
        parent = env
    elif tag == "box":
        parent = None
    else:
        raise OpError(f"apply of unknown source {tag}")

    param_names = []
    p = params
    while p is not None and p._tag == "link" and p._head is not None:
        if p._head._tag != "symbol":
            raise OpError(f"apply of non-symbol param {p._head._tag}")
        param_names.append(p._head.value)
        p = p._tail

    cost = sum(stack[-1 - i].size() for i in range(len(param_names)))
    machine.meter.charge_bytes(cost)

    apply_env = Env(data={}, parent=parent)
    for param_name in reversed(param_names):
        if not stack:
            raise OpError("stack underflow")
        arg = stack.pop()
        apply_env.data[param_name] = arg

    apply_stack = []
    result_stack = _evaluation(machine, body, apply_stack, apply_env)
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
