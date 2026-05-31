from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...machine.models.expression import Expr, resolve_list_exprs
from ...utils.integer import bytes_to_int
from .code import transaction_code_from_bytes

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
    if not isinstance(ver, Expr.Bytes):
        raise ValueError("invalid transaction version: expected Bytes")
    version = bytes_to_int(ver.value)
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

    detail_values: list[bytes] = []
    for n in body_nodes:
        if isinstance(n, Expr.Bytes):
            detail_values.append(n.value)
        else:
            raise ValueError(f"unexpected transaction body node type: {type(n).__name__}")

    (
        chain_id_bytes,
        amount_bytes,
        code_bytes,
        counter_bytes,
        cost_limit_bytes,
        data_bytes,
        recipient_bytes,
        sender_bytes,
    ) = detail_values

    tx = create_transaction(
        chain_id=bytes_to_int(chain_id_bytes),
        amount=bytes_to_int(amount_bytes),
        code=transaction_code_from_bytes(code_bytes),
        counter=bytes_to_int(counter_bytes),
        cost_limit=bytes_to_int(cost_limit_bytes),
        data=data_bytes,
        recipient=recipient_bytes,
        sender=sender_bytes,
        signature=signature_bytes,
        version=version,
        body_hash=body.hash(),
        atom_hash=bytes(transaction_id),
    )
    tx._expr = header
    return tx
