from __future__ import annotations

from typing import Optional

from astreum.expression import Expr, NIL
from astreum.consensus.transaction.code import TransactionCode
from astreum.consensus.transaction.model import Transaction


def create_transaction(
    chain_id: int,
    amount: int,
    counter: int,
    recipient: bytes,
    sender: bytes,
    cost_limit: int = 0,
    code: TransactionCode = TransactionCode.TRANSFER,
    signature: Optional[bytes] = None,
    body_hash: Optional[bytes] = None,
    expr_id: Optional[bytes] = None,
    data: Expr = NIL,
) -> Transaction:
    transaction = Transaction(
        chain_id=chain_id,
        amount=amount,
        code=code,
        counter=counter,
        cost_limit=cost_limit,
        data=data,
        recipient=recipient,
        sender=sender,
        signature=signature,
        body_hash=body_hash,
        expr_id=expr_id,
        hash=expr_id,
    )
    return transaction
