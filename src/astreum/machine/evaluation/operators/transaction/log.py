from astreum.machine.models.expression import NIL
from astreum.consensus.transaction.storage.pending import add_pending_storage_contract


def handle_stack_tx_log(machine, stack):
    value = stack.pop()
    fee = add_pending_storage_contract(
        machine.node, machine.block, None, None, value
    )
    if fee is None:
        raise RuntimeError("tx.log storage cost failed")
    machine.meter.charge(fee, kind="storage")
    machine.logs.append(value)
    machine.log_contract_entries.append(
        machine.block.pending_storage_contracts[-1]
    )
    stack.append(NIL)
