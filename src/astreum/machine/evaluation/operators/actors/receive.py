from typing import Any, List

from src.astreum.machine.models.expression import Expr, NIL


def handle_stack_receive(machine: Any, stack: List[Expr]) -> List[Expr]:
    target = stack.pop()
    if not isinstance(target, Expr.Symbol):
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return stack
    actor_name = target.value

    with machine.lock:
        mbox = machine.mailboxes.get(actor_name)
    if mbox is not None:
        msg = mbox.get()
        machine.meter.charge_bytes(target.size() + msg.size())
        stack.append(msg)
    else:
        machine.meter.charge_bytes(target.size() + 1)
        stack.append(NIL)

    return stack
