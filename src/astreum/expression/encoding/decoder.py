from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from astreum.expression.expr import Expr


def decode_expr_from_bytes(data: bytes) -> "Expr":
    """Decode an Expr from its byte representation.

    Args:
        data: The wire-format byte representation to decode.

    Returns:
        The decoded expression.

    Raises:
        ValueError: If data is empty or contains invalid wire format.
    """
    if not data:
        raise ValueError("empty bytes")
    tag = data[0]
    from astreum.expression.expr import Expr

    if tag == 0x00:
        if len(data) < 65:
            raise ValueError("link requires 65 bytes")
        return Expr("link", head_hash=data[1:33], tail_hash=data[33:65])
    elif tag == 0x01:
        return Expr("symbol", value=data[1:].decode("utf-8"))
    elif tag == 0x02:
        return Expr("bytes", value=data[1:])
    else:
        raise ValueError(f"unknown wire tag: {tag}")