from typing import List

from ...machine.models.expression import Expr


OBJECT_FOUND_ATOM_PAYLOAD = 1
OBJECT_FOUND_LIST_PAYLOAD = 2


def encode_object_found_expr_payload(expr: Expr) -> bytes:
    return bytes([OBJECT_FOUND_ATOM_PAYLOAD]) + expr.to_bytes()


def encode_object_found_expr_list_payload(exprs: List[Expr]) -> bytes:
    parts = [bytes([OBJECT_FOUND_LIST_PAYLOAD])]
    for expr in exprs:
        expr_bytes = expr.to_bytes()
        parts.append(len(expr_bytes).to_bytes(4, "big", signed=False))
        parts.append(expr_bytes)
    return b"".join(parts)


def decode_object_found_expr_list_payload(payload: bytes) -> List[Expr]:
    exprs: List[Expr] = []
    offset = 0
    while offset < len(payload):
        if len(payload) - offset < 4:
            raise ValueError("truncated expr length")
        expr_len = int.from_bytes(payload[offset : offset + 4], "big", signed=False)
        offset += 4
        if expr_len <= 0:
            raise ValueError("invalid expr length")
        end = offset + expr_len
        if end > len(payload):
            raise ValueError("truncated expr payload")
        exprs.append(Expr().from_bytes(payload[offset:end]))
        offset = end
    return exprs
