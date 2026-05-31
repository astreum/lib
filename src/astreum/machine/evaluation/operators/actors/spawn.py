from typing import Any, List

from src.astreum.machine.main import Machine
from src.astreum.machine.models.environment import Env
from src.astreum.machine.models.expression import Expr, NIL


def handle_stack_spawn(
    machine: "Machine", stack: List[Expr], env: Env
) -> List[Expr]:
    name_expr = stack.pop()
    body = stack.pop()

    machine.meter.charge_bytes(name_expr.size())

    if not isinstance(name_expr, Expr.Symbol):
        stack.append(Expr.Bytes(b"spawn: actor name must be a symbol"))
        return stack

    actor_name = name_expr.value

    if not isinstance(body, Expr.Link):
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return stack

    success = machine.spawn_actor(body, actor_name, env)
    if not success:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return stack

    stack.append(name_expr)
    return stack
