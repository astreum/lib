from typing import TYPE_CHECKING, List

from astreum.machine.environment import Env
from astreum.expression import Expr, NIL, link, str_, symbol
from astreum.machine import OpError

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def handle_stack_spawn(
    machine: "Machine", stack: List[Expr], env: Env
) -> List[Expr]:
    name_expr = stack.pop()
    body = stack.pop()

    machine.meter.charge_bytes(name_expr.size())

    if name_expr._tag != "symbol":
        raise OpError("spawn actor name must be a symbol")

    actor_name = name_expr.value

    if body._tag != "link":
        machine.meter.charge_bytes(1)
        raise OpError("spawn body must be a link")

    success = machine.spawn_actor(body, actor_name, env)
    if not success:
        machine.meter.charge_bytes(1)
        raise OpError("spawn failed")

    stack.append(name_expr)
    return stack


def handle_stack_spawn_with_result(machine, stack, env):
    try:
        stack = handle_stack_spawn(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
