from astreum.machine.models.expression import Expr, NIL, link, str_, symbol
from astreum.machine.models.op_error import OpError
from astreum.consensus.transaction.storage.pending import add_pending_storage_contract


def handle_stack_tx_log(machine, stack, env):
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


def handle_stack_tx_log_with_result(machine, stack, env):
    try:
        handle_stack_tx_log(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
