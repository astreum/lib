from typing import Any, List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_send(machine: Any, stack: List[Expr]) -> List[Expr]:
    msg = stack.pop()
    target = stack.pop()

    machine.meter.charge_bytes(target.size() + msg.size())

    if target._tag != "symbol":
        machine.meter.charge_bytes(1)
        raise OpError("send target must be a symbol")

    actor_name = target.value

    with machine.lock:
        mbox = machine.mailboxes.get(actor_name)

    if mbox is not None:
        mbox.put(msg)
    else:
        machine.meter.charge_bytes(1)
        raise OpError("send to unknown actor")

    return stack
