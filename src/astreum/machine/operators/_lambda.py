from typing import TYPE_CHECKING, List

from astreum.expression import Expr, NIL, link, symbol, str_
from astreum.machine import OpError

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def handle_stack_lambda(machine: "Machine", stack: List[Expr], env) -> None:
    if not stack:
        raise OpError("stack underflow")
    body = stack.pop()
    if not stack:
        raise OpError("stack underflow")
    params = stack.pop()

    if params._tag != "link":
        raise OpError(f"lambda of {params._tag}")

    machine.meter.charge_bytes(params.size() + body.size())

    env_uuid = machine.snapshot_env(env)
    env_uuid_expr = Expr("bytes", value=env_uuid.bytes)
    body_with_uuid = link(env_uuid_expr, body)
    lambda_val = link(link(body_with_uuid, params), symbol("lambda"))
    stack.append(lambda_val)


def handle_stack_lambda_with_result(machine, stack, env):
    try:
        handle_stack_lambda(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
