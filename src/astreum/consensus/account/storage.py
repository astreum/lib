from __future__ import annotations

from typing import Any

from ...machine.models.expression import Expr, resolve_list_exprs
from ...storage.actions.get import get_expr_list
from .create import create_account
from .model import Account


def get_account_from_storage(node: Any, expr_id: bytes) -> Account:
    header = get_expr_list(node, expr_id)
    if header is None:
        raise ValueError("unable to load account from storage")
    if not header._tag == "link":
        raise ValueError("account header must be a Link")

    header_nodes, missed = resolve_list_exprs(node, header)
    if missed:
        raise ValueError(
            f"unable to resolve account (missed={[h.hex()[:8] for h in missed]})"
        )
    if len(header_nodes) != 5:
        raise ValueError(
            f"malformed account length (got={len(header_nodes)}, expected=5)"
        )

    data_node, counter_node, code_node, channels_node, balance_node = header_nodes

    if not data_node._tag == "link":
        raise ValueError("expected Link for data_hash")
    if not counter_node._tag == "int":
        raise ValueError("expected Int for counter")
    if not code_node._tag == "link":
        raise ValueError("expected Link for code_hash")
    if not channels_node._tag == "link":
        raise ValueError("expected Link for channels_hash")
    if not balance_node._tag == "int":
        raise ValueError("expected Int for balance")

    account = create_account(
        balance=balance_node.value,
        data_hash=data_node._head_hash if data_node._head_hash is not None else data_node.hash(),
        channels_hash=channels_node._head_hash if channels_node._head_hash is not None else channels_node.hash(),
        counter=counter_node.value,
        code_hash=code_node._head_hash if code_node._head_hash is not None else code_node.hash(),
    )
    account._expr = header
    return account
