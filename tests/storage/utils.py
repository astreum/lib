from __future__ import annotations

import secrets

from astreum.communication.util import xor_distance
from astreum.machine.models.expression import Expr, bytes_list_to_expr


def generate_nearest_expr(
    peer_1_id: bytes,
    peer_2_id: bytes,
    *,
    max_attempts: int = 1000,
) -> Expr:
    """Return an Expr.Bytes whose hash is closer to peer_2_id than peer_1_id."""
    for _ in range(max_attempts):
        expr = Expr.Bytes(secrets.token_bytes(32))
        expr_id = expr.hash()
        if xor_distance(expr_id, peer_2_id) < xor_distance(expr_id, peer_1_id):
            return expr

    raise RuntimeError("Could not generate an expr closer to peer_2_id")


def generate_nearest_expr_list(
    peer_1_id: bytes,
    peer_2_id: bytes,
    list_size: int,
    *,
    max_attempts: int = 1000,
) -> Expr:
    """Return an Expr Link chain whose root hash is closer to peer_2_id than peer_1_id."""
    if list_size <= 0:
        raise ValueError("list_size must be greater than 0")

    payloads = [secrets.token_bytes(32) for _ in range(list_size)]
    payloads[0] = secrets.token_bytes(32)

    for _ in range(max_attempts):
        payloads[0] = secrets.token_bytes(32)
        chain = bytes_list_to_expr(payloads)
        if xor_distance(chain.hash(), peer_2_id) < xor_distance(chain.hash(), peer_1_id):
            return chain

    raise RuntimeError("Could not generate an expr list closer to peer_2_id")
