from astreum.machine.models.expression import bytes_, NIL


def handle_stack_acc_get(machine, stack):
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