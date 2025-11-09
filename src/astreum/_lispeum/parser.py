from typing import List, Tuple
from . import Expr

class ParseError(Exception):
    pass

def _parse_one(tokens: List[str], pos: int = 0) -> Tuple[Expr, int]:
    if pos >= len(tokens):
        raise ParseError("unexpected end")
    tok = tokens[pos]

    if tok == '(':  # list
        items: List[Expr] = []
        i = pos + 1
        while i < len(tokens):
            if tokens[i] == ')':
                return Expr.ListExpr(items), i + 1
            expr, i = _parse_one(tokens, i)
            items.append(expr)
        raise ParseError("expected ')'")

    if tok == ')':
        raise ParseError("unexpected ')'")

    # try integer → Bytes (variable-length two's complement)
    try:
        n = int(tok)
        # encode as minimal-width signed two's complement, big-endian
        def int_to_min_tc(v: int) -> bytes:
            """Return the minimal-width signed two's complement big-endian
            byte encoding of integer v. Width expands just enough so that
            decoding with signed=True yields the same value and sign.
            Example: 0 -> b"\x00", 127 -> b"\x7f", 128 -> b"\x00\x80".
            """
            if v == 0:
                return b"\x00"
            w = 1
            while True:
                try:
                    return v.to_bytes(w, "big", signed=True)
                except OverflowError:
                    w += 1

        return Expr.Bytes(int_to_min_tc(n)), pos + 1
    except ValueError:
        return Expr.Symbol(tok), pos + 1

def parse(tokens: List[str]) -> Tuple[Expr, List[str]]:
    """Parse tokens into an Expr and return (expr, remaining_tokens)."""
    expr, next_pos = _parse_one(tokens, 0)
    return expr, tokens[next_pos:]
