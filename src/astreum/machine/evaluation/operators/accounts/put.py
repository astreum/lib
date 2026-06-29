from astreum.consensus.block.rate import calculate_storage_fee
from astreum.consensus.transaction.storage.pending import add_pending_storage_contract
from astreum.machine.models.expression import Expr, ZERO32
from astreum.validation.constants import BURN_ADDRESS


def _load_acct(machine, addr):
    if addr in machine.accounts:
        return machine.accounts[addr]
    acct = machine.block.accounts.get_account(addr, machine.node)
    if acct is not None:
        acct = acct.clone()
        machine.accounts[addr] = acct
    return acct


def handle_stack_acc_put(machine, stack):
    value_expr = stack.pop()
    key_expr = stack.pop()
    if key_expr._tag != "bytes" or value_expr._tag != "bytes":
        raise RuntimeError("acc.put: expected Bytes")
    key = key_expr.value
    value = value_expr.value

    expression_account = machine.accounts.get(machine.tx.recipient)
    if expression_account is None:
        raise RuntimeError("acc.put: expression account not found")

    sender_account = _load_acct(machine, machine.tx.sender)
    burn_account = _load_acct(machine, BURN_ADDRESS)

    storage_fee = calculate_storage_fee(machine.block, len(key) + len(value))
    if sender_account.balance < storage_fee:
        raise RuntimeError("acc.put: sender cannot afford storage fee")

    sender_account.balance -= storage_fee
    burn_account.balance += storage_fee

    expression_account.data.put(machine.node, key, value_expr)
    expression_account.data_hash = expression_account.data.root_hash or ZERO32

    add_pending_storage_contract(
        machine.node, machine.block, machine.tx.recipient, key, value_expr,
    )

    machine.accounts[machine.tx.recipient] = expression_account
    machine.accounts[machine.tx.sender] = sender_account
    machine.accounts[BURN_ADDRESS] = burn_account

    machine.meter.charge_bytes(len(key) + len(value))
