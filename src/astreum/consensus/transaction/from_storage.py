from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...machine.models.expression import Expr, resolve_list_exprs
from ...storage.actions.get import get_expr_list
from .code import TransactionCode

if TYPE_CHECKING:
    from .model import Transaction


def get_transaction_from_storage(
    node: Any,
    transaction_id: bytes,
) -> "Transaction":
    from .create import create_transaction

    header = get_expr_list(node, transaction_id)
    if header is None:
        raise ValueError("unable to load transaction from storage")
    if not header._tag == "link":
        raise ValueError("transaction header must be a Link")
    if header._tail is None or header._tail._tag != "symbol" or header._tail.value != "transaction":
        raise ValueError(
            f"invalid transaction type tag (got {header._tail!r})"
        )

    inner = header._head
    if inner is None or inner._tag != "link":
        raise ValueError("transaction inner header must be a Link")

    inner_nodes, missed = resolve_list_exprs(node, inner)
    if missed:
        raise ValueError(
            f"unable to resolve transaction header (missed={[h.hex()[:8] for h in missed]})"
        )
    if len(inner_nodes) != 2:
        raise ValueError(
            f"malformed transaction header length (got={len(inner_nodes)}, expected=2)"
        )

    body, sig = inner_nodes
    if not sig._tag == "bytes":
        raise ValueError("invalid transaction signature: expected Bytes")
    signature_bytes = sig.value
    if not body._tag == "link":
        raise ValueError("transaction body must be a Link chain")

    body_nodes, missed = resolve_list_exprs(node, body)
    if missed:
        raise ValueError(
            f"unable to resolve transaction body (missed={[h.hex()[:8] for h in missed]})"
        )
    if len(body_nodes) != 9:
        raise ValueError(
            f"malformed transaction body length (got={len(body_nodes)}, expected=9)"
        )

    (
        version_node,
        amount_node,
        chain_id_node,
        code_node,
        cost_limit_node,
        counter_node,
        data_node,
        recipient_node,
        sender_node,
    ) = body_nodes

    if not version_node._tag == "int":
        raise ValueError("expected Int for version")
    version = version_node.value
    if version != 1:
        raise ValueError(f"unsupported transaction version (version={version})")
    if not amount_node._tag == "int":
        raise ValueError("expected Int for amount")
    if not chain_id_node._tag == "int":
        raise ValueError("expected Int for chain_id")
    if not code_node._tag == "int":
        raise ValueError("expected Int for code")
    if not cost_limit_node._tag == "int":
        raise ValueError("expected Int for cost_limit")
    if not counter_node._tag == "int":
        raise ValueError("expected Int for counter")
    if not recipient_node._tag == "bytes":
        raise ValueError("expected Bytes for recipient")
    if not sender_node._tag == "bytes":
        raise ValueError("expected Bytes for sender")

    tx = create_transaction(
        chain_id=chain_id_node.value,
        amount=amount_node.value,
        code=TransactionCode(code_node.value),
        counter=counter_node.value,
        cost_limit=cost_limit_node.value,
        data=data_node,
        recipient=recipient_node.value,
        sender=sender_node.value,
        signature=signature_bytes,
        version=version,
        body_hash=body.hash(),
        expr_id=transaction_id,
    )
    tx._expr = header
    return tx
