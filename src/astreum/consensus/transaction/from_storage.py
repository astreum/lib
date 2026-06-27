from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...machine.models.expression import Expr, resolve_list_exprs
from .code import TransactionCode

if TYPE_CHECKING:
    from .model import Transaction


def get_transaction_from_storage(
    node: Any,
    transaction_id: bytes,
) -> "Transaction":
    from .create import create_transaction

    header = node.get_expr_list(transaction_id)
    if header is None:
        raise ValueError("unable to load transaction from storage")
    if not isinstance(header, Expr.Link):
        raise ValueError("transaction header must be a Link")

    header_nodes, missed = resolve_list_exprs(node, header)
    if missed:
        raise ValueError(
            f"unable to resolve transaction header (missed={[h.hex()[:8] for h in missed]})"
        )
    if len(header_nodes) != 4:
        raise ValueError(
            f"malformed transaction header length (got={len(header_nodes)}, expected=4)"
        )

    body, sig, ver, terminal = header_nodes
    if not isinstance(terminal, Expr.Symbol) or terminal.value != "transaction":
        raise ValueError(
            f"invalid transaction header terminal (expected Symbol('transaction'), got {terminal!r})"
        )
    if not isinstance(sig, Expr.Bytes):
        raise ValueError("invalid transaction signature: expected Bytes")
    signature_bytes = sig.value
    if not isinstance(ver, Expr.Int):
        raise ValueError("invalid transaction version: expected Int")
    version = ver.value
    if version != 1:
        raise ValueError(f"unsupported transaction version (version={version})")
    if not isinstance(body, Expr.Link):
        raise ValueError("transaction body must be a Link chain")

    body_nodes, missed = resolve_list_exprs(node, body)
    if missed:
        raise ValueError(
            f"unable to resolve transaction body (missed={[h.hex()[:8] for h in missed]})"
        )
    if len(body_nodes) != 8:
        raise ValueError(
            f"malformed transaction body length (got={len(body_nodes)}, expected=8)"
        )

    (
        amount_node,
        chain_id_node,
        code_node,
        cost_limit_node,
        counter_node,
        data_node,
        recipient_node,
        sender_node,
    ) = body_nodes

    if not isinstance(amount_node, Expr.Int):
        raise ValueError("expected Int for amount")
    if not isinstance(chain_id_node, Expr.Int):
        raise ValueError("expected Int for chain_id")
    if not isinstance(code_node, Expr.Int):
        raise ValueError("expected Int for code")
    if not isinstance(cost_limit_node, Expr.Int):
        raise ValueError("expected Int for cost_limit")
    if not isinstance(counter_node, Expr.Int):
        raise ValueError("expected Int for counter")
    if not isinstance(recipient_node, Expr.Bytes):
        raise ValueError("expected Bytes for recipient")
    if not isinstance(sender_node, Expr.Bytes):
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
        atom_hash=bytes(transaction_id),
    )
    tx._expr = header
    return tx
