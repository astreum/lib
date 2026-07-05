from typing import TYPE_CHECKING, List

from astreum.machine.models.expression import Expr, NIL, Closure
from astreum.machine.models.op_error import OpError

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

    param_list = []
    p = params
    while p._tag == "link" and p._head is not None:
        param_list.append(p._head.value)
        if p._tail is None or p._tail is NIL:
            break
        p = p._tail

    machine.meter.charge_bytes(params.size() + body.size())

    env_uuid = machine.snapshot_env(env)

    closure = Closure(
        params=param_list,
        body=body,
        captured_env_uuid=env_uuid,
    )
    stack.append(Expr("closure", value=closure))
