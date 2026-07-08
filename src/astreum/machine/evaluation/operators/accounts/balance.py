from astreum.machine.models.expression import Expr, NIL, int_, link, str_, symbol
from astreum.machine.models.op_error import OpError


def handle_stack_acc_balance(machine, stack, env):
    expression_account = machine.block.accounts.get_account(machine.tx.recipient, machine.node)
    if expression_account is None:
        raise RuntimeError("acc.balance: expression account not found")
    stack.append(int_(expression_account.balance))
    machine.meter.charge_bytes(1)


def handle_stack_acc_balance_with_result(machine, stack, env):
    try:
        handle_stack_acc_balance(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))