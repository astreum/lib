from typing import TYPE_CHECKING, List

from astreum.machine.models.environment import Env
from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def handle_stack_spawn(
    machine: "Machine", stack: List[Expr], env: Env
) -> List[Expr]:
    name_expr = stack.pop()
    body = stack.pop()

    machine.meter.charge_bytes(name_expr.size())

    if not isinstance(name_expr, Expr.Symbol):
        raise OpError("spawn actor name must be a symbol")

    actor_name = name_expr.value

    if not isinstance(body, Expr.Link):
        machine.meter.charge_bytes(1)
        raise OpError("spawn body must be a link")

    success = machine.spawn_actor(body, actor_name, env)
    if not success:
        machine.meter.charge_bytes(1)
        raise OpError("spawn failed")

    stack.append(name_expr)
    return stack
