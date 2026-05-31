from typing import List

from src.astreum.machine.models.environment import Env
from src.astreum.machine.models.expression import Expr, NIL


def handle_stack_def(machine, stack: List[Expr], env: Env) -> None:
    name = stack.pop()
    value = stack.pop()

    # Charge: symbol utf8 bytes + serialized value bytes
    cost = name.size() + value.size()
    machine.meter.charge_bytes(cost)

    if not isinstance(name, Expr.Symbol):
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return
    env.put(key=name.value, value=value)
