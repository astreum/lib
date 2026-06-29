from astreum.consensus.account import create_account
from astreum.consensus.block.rate import calculate_storage_fee
from astreum.consensus.transaction.storage.pending import add_pending_storage_contract
from astreum.machine.models.expression import Expr
from astreum.validation.constants import BURN_ADDRESS


def _load_acct(machine, addr):
    if addr in machine.accounts:
        return machine.accounts[addr]
    acct = machine.block.accounts.get_account(addr, machine.node)
    if acct is not None:
        acct = acct.clone()
        machine.accounts[addr] = acct
    return acct


def handle_stack_acc_pay(machine, stack):
    amount_expr = stack.pop()
    recipient_expr = stack.pop()
    if amount_expr._tag != "int" or recipient_expr._tag != "bytes":
        raise RuntimeError("acc.pay: expected Int amount and Bytes recipient")
    amount = amount_expr.value
    recipient_addr = recipient_expr.value

    expression_account = machine.accounts.get(machine.tx.recipient)
    if expression_account is None:
        raise RuntimeError("acc.pay: expression account not found")

    sender_account = _load_acct(machine, machine.tx.sender)
    burn_account = _load_acct(machine, BURN_ADDRESS)
    recipient_account = _load_acct(machine, recipient_addr)

    is_new_recipient = recipient_account is None
    if is_new_recipient:
        recipient_account = create_account()
        machine.accounts[recipient_addr] = recipient_account

    new_account_storage_fee = 0
    if is_new_recipient:
        new_account_storage_fee = calculate_storage_fee(
            machine.block, recipient_account.expr().size(),
        )

    total_deduction = amount + new_account_storage_fee
    if expression_account.balance < total_deduction:
        raise RuntimeError("acc.pay: insufficient balance")

    if sender_account.balance < new_account_storage_fee:
        raise RuntimeError("acc.pay: sender cannot afford storage fee")

    expression_account.balance -= total_deduction
    sender_account.balance -= new_account_storage_fee
    burn_account.balance += new_account_storage_fee
    recipient_account.balance += amount

    if is_new_recipient:
        add_pending_storage_contract(
            machine.node, machine.block, recipient_addr, None, recipient_account.expr(),
        )

    machine.accounts[machine.tx.recipient] = expression_account
    machine.accounts[machine.tx.sender] = sender_account
    machine.accounts[BURN_ADDRESS] = burn_account
    machine.accounts[recipient_addr] = recipient_account
