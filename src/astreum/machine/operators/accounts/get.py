from astreum.expression import Expr, NIL, bytes_, link, str_, symbol
from astreum.machine import OpError


def handle_stack_acc_get(machine, stack, env):
    key_expr = stack.pop()
    if key_expr._tag != "bytes":
        raise RuntimeError("acc.get: expected Bytes key")
    key = key_expr.value

    expression_account = machine.block.accounts.get_account(machine.tx.recipient, machine.node)
    if expression_account is None:
        raise RuntimeError("acc.get: expression account not found")

    value = expression_account.data.get(machine.node, key)
    if value is None:
        stack.append(NIL)
    else:
        stack.append(bytes_(value))

    machine.meter.charge_bytes(len(key))


def handle_stack_acc_get_with_result(machine, stack, env):
    try:
        handle_stack_acc_get(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))