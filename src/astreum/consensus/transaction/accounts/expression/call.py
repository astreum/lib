from __future__ import annotations

import uuid
from typing import Any, Dict, Optional, Tuple

from .....machine.models.environment import Env
from .....machine.models.expression import ERROR_SYMBOL, Expr
from .....machine.models.meter import Meter
from .....machine.models.expression import ZERO32
from .....utils.integer import int_to_bytes
from .....validation.models.receipt import STATUS_FAILED, STATUS_SUCCESS
from ....account import create_account


def _is_error(expr: Expr) -> bool:
    return (
        isinstance(expr, Expr.ListExpr)
        and bool(expr.elements)
        and isinstance(expr.elements[0], Expr.Symbol)
        and expr.elements[0].value == ERROR_SYMBOL
    )


def _bytes_expr(expr: Expr) -> Optional[bytes]:
    if isinstance(expr, Expr.Bytes):
        return expr.value
    return None


def _amount_expr(expr: Expr) -> Optional[int]:
    raw = _bytes_expr(expr)
    if raw is None:
        return None
    if not raw:
        return 0
    value = int.from_bytes(raw, "big", signed=True)
    if value < 0:
        return None
    return value


def handle_expression_account_call(
    node: Any,
    block: Any,
    transaction: Any,
) -> Tuple[int, int]:
    meter = Meter(limit=int(transaction.cost_limit))
    working_accounts: Dict[bytes, Any] = {}

    def get_working_account(address: bytes, *, create_missing: bool = True) -> Any:
        cached = working_accounts.get(address)
        if cached is not None:
            return cached

        live_account = block.accounts.get_account(address=address, node=node)
        if live_account is None:
            if not create_missing:
                return None
            account = create_account()
        else:
            account = live_account.clone()
        working_accounts[address] = account
        return account

    expression_account = get_working_account(transaction.recipient, create_missing=False)
    if expression_account is None or expression_account.code_hash == ZERO32:
        return STATUS_FAILED, meter.used

    program_expr = node.get_expr(expression_account.code_hash)
    if program_expr is None:
        return STATUS_FAILED, meter.used
    current_expr = Expr.ListExpr([
        Expr.Bytes(transaction.data),
        program_expr,
    ])

    expression_account.balance += int(transaction.amount)

    call_env_id = uuid.uuid4()
    node.environments[call_env_id] = Env()
    try:
        node.env_set(call_env_id, "tx.sender", Expr.Bytes(transaction.sender))
        node.env_set(call_env_id, "tx.value", Expr.Bytes(int_to_bytes(transaction.amount)))
        node.env_set(call_env_id, "acc.self", Expr.Bytes(transaction.recipient))

        while True:
            result = node.high_eval(expr=current_expr, env_id=call_env_id, meter=meter)
            if _is_error(result):
                return STATUS_FAILED, meter.used

            control = result.elements[-1].value if isinstance(result, Expr.ListExpr) and result.elements and isinstance(result.elements[-1], Expr.Symbol) else None

            if control == "acc.pay":
                if len(result.elements) != 4:
                    return STATUS_FAILED, meter.used
                recipient = _bytes_expr(result.elements[0])
                amount = _amount_expr(result.elements[1])
                next_expr = result.elements[2]
                if recipient is None or amount is None:
                    return STATUS_FAILED, meter.used
                if expression_account.balance < amount:
                    return STATUS_FAILED, meter.used

                recipient_account = get_working_account(recipient)
                expression_account.balance -= amount
                recipient_account.balance += amount
                current_expr = next_expr
                continue

            if control == "acc.get":
                if len(result.elements) != 3:
                    return STATUS_FAILED, meter.used
                key = _bytes_expr(result.elements[0])
                if key is None:
                    return STATUS_FAILED, meter.used
                try:
                    value = expression_account.data.get(node, key)
                except Exception:
                    return STATUS_FAILED, meter.used
                if value is None:
                    current_expr = Expr.ListExpr([
                        Expr.ListExpr([]),
                        result.elements[1],
                    ])
                else:
                    current_expr = Expr.ListExpr([
                        Expr.Bytes(value),
                        result.elements[1],
                    ])
                continue

            if control == "acc.put":
                if len(result.elements) != 4:
                    return STATUS_FAILED, meter.used
                key = _bytes_expr(result.elements[0])
                value = _bytes_expr(result.elements[1])
                if key is None or value is None:
                    return STATUS_FAILED, meter.used
                try:
                    expression_account.data.put(node, key, value)
                except Exception:
                    return STATUS_FAILED, meter.used
                expression_account.data_hash = expression_account.data.root_hash or ZERO32
                current_expr = result.elements[2]
                continue

            for address, account in working_accounts.items():
                block.accounts.set_account(address, account)
            return STATUS_SUCCESS, meter.used
    finally:
        node.environments.pop(call_env_id, None)
