from typing import Any, List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_send(machine: Any, stack: List[Expr]) -> List[Expr]:
    msg = stack.pop()
    target = stack.pop()

    machine.meter.charge_bytes(target.size() + msg.size())

    if not isinstance(target, Expr.Symbol):
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return stack

    actor_name = target.value

    with machine.lock:
        mbox = machine.mailboxes.get(actor_name)

    if mbox is not None:
        mbox.put(msg)
    else:
        machine.meter.charge_bytes(1)
        stack.append(NIL)

    return stack
