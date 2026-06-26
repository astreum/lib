from astreum.machine.models.expression import Expr
from astreum.utils.integer import int_to_bytes


def handle_stack_acc_balance(machine, stack):
    expression_account = machine.accounts.get(machine.tx.recipient)
    if expression_account is None:
        raise RuntimeError("acc.balance: expression account not found")
    stack.append(Expr.Bytes(int_to_bytes(expression_account.balance)))
    machine.meter.charge_bytes(1)
