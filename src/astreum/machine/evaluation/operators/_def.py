from typing import List

from astreum.machine.models.environment import Env
from astreum.machine.models.expression import Expr, NIL
from astreum.machine.models.op_error import OpError


def handle_stack_def(machine, stack: List[Expr], env: Env) -> None:
    if len(stack) < 2:
        raise OpError("stack underflow")

    name = stack.pop()
    value = stack.pop()

    if name._tag != "symbol":
        raise OpError(f"def of {name._tag}")

    # Charge: symbol utf8 bytes + serialized value bytes
    cost = name.size() + value.size()
    machine.meter.charge_bytes(cost)

    target = env.def_target if env.def_target is not None else env
    if name.value in target.data:
        raise OpError("def already exists")

    target.put(key=name.value, value=value)
