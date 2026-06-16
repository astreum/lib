from __future__ import annotations

from .link import Link, ZERO32
from .symbol import Symbol
from .bytes_ import Bytes
from .helpers import NIL, bytes_list_to_expr, link_list_to_expr, \
    resolve_list_exprs, resolve_inner_exprs


class Expr:
    Link = Link
    Symbol = Symbol
    Bytes = Bytes

    def from_bytes(self, data: bytes) -> Expr:
        if not data:
            raise ValueError("empty bytes")
        tag = data[0]
        if tag == 0x00:
            if len(data) < 65:
                raise ValueError(
                    "Link byte format requires 65 bytes: [1 tag] [32 head] [32 tail]"
                )
            return self.Link(head_hash=data[1:33], tail_hash=data[33:65])
        elif tag == 0x01:
            return self.Symbol(data[1:].decode("utf-8"))
        elif tag == 0x02:
            return self.Bytes(data[1:])
        raise ValueError(f"unknown expression tag: {tag}")


__all__ = [
    "Expr",
    "NIL",
    "ZERO32",
    "bytes_list_to_expr",
    "link_list_to_expr",
    "resolve_list_exprs",
    "resolve_inner_exprs",
]
