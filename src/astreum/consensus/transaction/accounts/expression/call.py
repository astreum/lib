from __future__ import annotations

from typing import Any, Tuple

from .....machine.models.expression import Expr, NIL, ZERO32
from .....machine.models.meter import MeterExceededError
from .....machine.main import Machine

from .....validation.models.receipt import STATUS_FAILED, STATUS_SUCCESS


def handle_expression_account_call(
    node: Any,
    block: Any,
    transaction: Any,
) -> Tuple[int, int]:
    machine = Machine(
        node=node,
        mode="deterministic",
        meter_limit=int(transaction.cost_limit),
    )
    machine.tx = transaction
    machine.block = block

    expression_account = block.accounts.get_account(transaction.recipient, node)
    if expression_account is None or expression_account.code_hash == ZERO32:
        return STATUS_FAILED, machine.meter.used
    expression_account = expression_account.clone()
    expression_account.balance += int(transaction.amount)
    machine.accounts[transaction.recipient] = expression_account

    program_expr = node.get_expr(expression_account.code_hash)
    if program_expr is None:
        return STATUS_FAILED, machine.meter.used

    contract_start = len(block.pending_storage_contracts)

    try:
        data_expr = Expr().from_bytes(transaction.data) if transaction.data else NIL
        machine.run(Expr.Link(data_expr, program_expr))
    except (MeterExceededError, RuntimeError):
        pending = block.pending_storage_contracts
        reverted = pending[contract_start:]
        reverted_ids = {c.record_id for c in reverted} | {
            sid for c in reverted for sid, _ in c.slot_entries
        }
        del pending[contract_start:]
        for entry in pending:
            entry.locked = [lid for lid in entry.locked if lid not in reverted_ids]
        return STATUS_FAILED, machine.meter.used

    for addr, acct in machine.accounts.items():
        block.accounts.set_account(addr, acct)
    return STATUS_SUCCESS, machine.meter.used
