from astreum.consensus.block.rate import calculate_storage_fee
from astreum.consensus.transaction.storage.pending import add_pending_storage_contract
from astreum.machine.models.expression import ZERO32
from astreum.consensus.constants import STORAGE_ADDRESS


def handle_stack_acc_put(machine, stack):
    value_expr = stack.pop()
    key_expr = stack.pop()
    if key_expr._tag != "bytes" or value_expr._tag != "bytes":
        raise RuntimeError("acc.put: expected Bytes")
    key = key_expr.value
    value = value_expr.value

    expression_account = machine.block.accounts.get_account(machine.tx.recipient, machine.node)
    if expression_account is None:
        raise RuntimeError("acc.put: expression account not found")

    sender_account = machine.block.accounts.get_account(machine.tx.sender, machine.node)
    if sender_account is None:
        raise RuntimeError("acc.put: sender account not found")
    storage_account = machine.block.accounts.get_account(STORAGE_ADDRESS, machine.node)

    storage_fee = calculate_storage_fee(machine.block, len(key) + len(value))
    if sender_account.balance < storage_fee:
        raise RuntimeError("acc.put: sender cannot afford storage fee")

    sender_account.balance -= storage_fee
    storage_account.balance += storage_fee

    expression_account.data.put(machine.node, key, value_expr)
    expression_account.data_hash = expression_account.data.root_hash or ZERO32

    add_pending_storage_contract(
        machine.node, machine.block, machine.tx.recipient, key, value_expr,
    )

    machine.block.accounts.set_account(machine.tx.recipient, expression_account)
    machine.block.accounts.set_account(machine.tx.sender, sender_account)
    machine.block.accounts.set_account(STORAGE_ADDRESS, storage_account)

    machine.meter.charge_bytes(len(key) + len(value))