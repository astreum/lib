from __future__ import annotations

from typing import Any

from ...machine.models.expression import Expr, resolve_list_exprs
from ...utils.integer import bytes_to_int
from .create import create_account
from .model import Account


def get_account_from_storage(node: Any, expr_id: bytes) -> Account:
    header = node.get_expr_list(expr_id)
    if header is None:
        raise ValueError("unable to load account from storage")
    if not isinstance(header, Expr.Link):
        raise ValueError("account header must be a Link")

    header_nodes, missed = resolve_list_exprs(node, header)
    if missed:
        raise ValueError(
            f"unable to resolve account (missed={[h.hex()[:8] for h in missed]})"
        )
    if len(header_nodes) != 6:
        raise ValueError(
            f"malformed account length (got={len(header_nodes)}, expected=6)"
        )

    data_node, counter_node, code_node, channels_node, balance_node, terminal = header_nodes
    if not isinstance(terminal, Expr.Symbol) or terminal.value != "account":
        raise ValueError(
            f"invalid account terminal (expected Symbol('account'), got {terminal!r})"
        )

    detail_values: list[bytes] = []
    for n in (data_node, counter_node, code_node, channels_node, balance_node):
        if isinstance(n, Expr.Bytes):
            detail_values.append(n.value)
        elif isinstance(n, Expr.Link):
            detail_values.append(n.head_hash if n.head_hash is not None else n.hash())
        else:
            raise ValueError(f"unexpected account node type: {type(n).__name__}")

    data_bytes, counter_bytes, code_bytes, channels_bytes, balance_bytes = detail_values

    account = create_account(
        balance=bytes_to_int(balance_bytes),
        data_hash=data_bytes,
        channels_hash=channels_bytes,
        counter=bytes_to_int(counter_bytes),
        code_hash=code_bytes,
    )
    account._expr = header
    return account
