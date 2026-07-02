from astreum.machine.models.expression import int_


def handle_stack_acc_balance(machine, stack):
    expression_account = machine.block.accounts.get_account(machine.tx.recipient, machine.node)
    if expression_account is None:
        raise RuntimeError("acc.balance: expression account not found")
    stack.append(int_(expression_account.balance))
    machine.meter.charge_bytes(1)