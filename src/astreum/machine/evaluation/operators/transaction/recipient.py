from astreum.machine.models.expression import Expr, NIL, bytes_, link, str_, symbol
from astreum.machine.models.op_error import OpError


def handle_stack_tx_recipient(machine, stack, env):
    value = machine.tx.recipient
    stack.append(bytes_(value))
    machine.meter.charge_bytes(len(value))


def handle_stack_tx_recipient_with_result(machine, stack, env):
    try:
        handle_stack_tx_recipient(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
