from __future__ import annotations

from typing import Any, Tuple

from .....machine.models.expression import Expr, NIL, ZERO32, link
from .....machine.models.meter import MeterExceededError
from .....machine.main import Machine
from ...storage.pending import (
    add_pending_storage_contract,
    remove_pending_storage_contract,
)

from .....validation.models.receipt import STATUS_FAILED, STATUS_SUCCESS


def handle_expression_account_call(
    node: Any,
    block: Any,
    transaction: Any,
) -> Tuple[int, int, list]:
    machine = Machine(
        node=node,
        mode="deterministic",
        meter_limit=int(transaction.cost_limit),
    )
    machine.tx = transaction
    machine.block = block

    expression_account = block.accounts.get_account(transaction.recipient, node)
    if expression_account is None or expression_account.code_hash == ZERO32:
        return STATUS_FAILED, machine.meter.eval, []

    expression_account = expression_account.clone()
    expression_account.balance += int(transaction.amount)
    machine.accounts[transaction.recipient] = expression_account

    program_expr = node.get_expr(expression_account.code_hash)
    if program_expr is None:
        return STATUS_FAILED, machine.meter.eval, []
    contract_start = len(block.pending_storage_contracts)

    try:
        data_expr = Expr.from_bytes(transaction.data) if transaction.data else NIL
        machine.run(link(data_expr, program_expr))
    except (MeterExceededError, RuntimeError):
        pending = block.pending_storage_contracts
        reverted = pending[contract_start:]
        reverted_ids = {c.record_id for c in reverted} | {
            sid for c in reverted for sid, _ in c.slot_entries
        }
        del pending[contract_start:]
        for entry in pending:
            entry.locked = [lid for lid in entry.locked if lid not in reverted_ids]
        logs = machine.logs
        return STATUS_FAILED, machine.meter.eval, logs

    for addr, acct in machine.accounts.items():
        block.accounts.set_account(addr, acct)
    logs = machine.logs
    for entry in machine.log_contract_entries:
        remove_pending_storage_contract(block, entry)
    return STATUS_SUCCESS, machine.meter.eval, logs
