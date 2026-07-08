from typing import Any, List

from astreum.machine.models.expression import Expr, NIL, link, str_, symbol
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


def handle_stack_send_with_result(machine, stack):
    try:
        stack = handle_stack_send(machine, stack)
        top = stack.pop()
        stack.append(link(top, symbol("ok")))
        return stack
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
        return stack
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
        return stack
