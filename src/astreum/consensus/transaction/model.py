from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from ...machine.models.expression import Expr, NIL, link, int_, bytes_, symbol
from .code import TransactionCode


@dataclass
class Transaction:
    chain_id: int
    amount: int
    code: TransactionCode
    counter: int
    cost_limit: int = 0
    version: int = 1
    data: Expr = NIL
    recipient: bytes = b""
    sender: bytes = b""
    signature: Optional[bytes] = None
    atom_hash: Optional[bytes] = None
    body_hash: Optional[bytes] = None
    hash: Optional[bytes] = None
    block_hash: Optional[bytes] = None
    _expr: Optional["Expr"] = field(default=None, repr=False)

    def sign(self, private_key: Any) -> bytes:
        """Sign the transaction detail list head and store the signature."""
        body: Expr = bytes_(bytes(self.sender))
        body = link(bytes_(bytes(self.recipient)), body)
        body = link(self.data, body)
        body = link(int_(self.cost_limit), body)
        body = link(int_(self.counter), body)
        body = link(int_(int(self.code)), body)
        body = link(int_(self.amount), body)
        body = link(int_(self.chain_id), body)

        body_hash = body.hash()
        self.signature = private_key.sign(body_hash)
        self.body_hash = body_hash
        self.atom_hash = None
        self.hash = None
        return body_hash

    def to_expr(self) -> Expr:
        # Body Link chain from innermost to outermost (alphabetical field order).
        # resolve_list_exprs flattens this to amount..sender.
        body: Expr = bytes_(bytes(self.sender))
        body = link(bytes_(bytes(self.recipient)), body)
        body = link(self.data, body)
        body = link(int_(self.counter), body)
        body = link(int_(self.cost_limit), body)
        body = link(int_(int(self.code)), body)
        body = link(int_(self.chain_id), body)
        body = link(int_(self.amount), body)
        return link(
            body,
            link(
                bytes_(bytes(self.signature or b"")),
                link(
                    int_(self.version),
                    symbol("transaction"))))

    def expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        self._expr = self.to_expr()
        return self._expr
