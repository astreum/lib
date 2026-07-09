from typing import Any, List

from astreum.expression import Expr, NIL, link, str_, symbol
from astreum.machine import OpError


def handle_stack_receive(machine: Any, stack: List[Expr]) -> List[Expr]:
    target = stack.pop()
    if target._tag != "symbol":
        machine.meter.charge_bytes(1)
        raise OpError("receive target must be a symbol")
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


def handle_stack_receive_with_result(machine, stack):
    try:
        stack = handle_stack_receive(machine, stack)
        top = stack.pop()
        stack.append(link(top, symbol("ok")))
        return stack
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
        return stack
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
        return stack
