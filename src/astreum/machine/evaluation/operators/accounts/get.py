from astreum.machine.models.expression import Expr, NIL


def handle_stack_acc_get(machine, stack):
    key_expr = stack.pop()
    if not isinstance(key_expr, Expr.Bytes):
        raise RuntimeError("acc.get: expected Bytes key")
    key = key_expr.value

    expression_account = machine.accounts.get(machine.tx.recipient)
    if expression_account is None:
        raise RuntimeError("acc.get: expression account not found")

    value = expression_account.data.get(machine.node, key)
    if value is None:
        stack.append(NIL)
    else:
        stack.append(Expr.Bytes(value))

    machine.meter.charge_bytes(len(key))
