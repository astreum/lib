from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from astreum.expression.expr import Expr


ZERO32 = b"\x00" * 32


def encode_expr_to_bytes(expr: "Expr") -> bytes:
    """Encode an Expr to its byte representation.

    Args:
        expr: The expression to encode.

    Returns:
        The wire-format byte representation of the expression.

    Raises:
        TypeError: If expr is a closure (closures cannot be serialized).
    """
    if expr._tag == "link":
        hh = expr._head_hash
        if hh is None:
            hh = expr._head.hash() if expr._head is not None else ZERO32
        th = expr._tail_hash
        if th is None:
            th = expr._tail.hash() if expr._tail is not None else ZERO32
        return b"\x00" + hh + th

    if expr._tag == "symbol":
        val = expr._value.encode("utf-8")
        return b"\x01" + val

    if expr._tag == "bytes":
        return b"\x02" + expr._value

    from astreum.expression.expr import TAG_BYTE_ENCODINGS, Expr, link

    encoder = TAG_BYTE_ENCODINGS.get(expr._tag)
    if encoder is not None:
        head = Expr("bytes", value=encoder(expr._value))
        tail = Expr("symbol", value=expr._tag)
        return encode_expr_to_bytes(link(head, tail))

    head = expr._value if expr._value is not None else link(None, None)
    tail = Expr("symbol", value=expr._tag)
    return encode_expr_to_bytes(link(head, tail))