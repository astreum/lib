from typing import List, Tuple
from src.astreum._lispeum import Expr

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
                # special-case error form at close: (origin topic err) or (topic err)
                if len(items) >= 3 and isinstance(items[-1], Expr.Symbol) and items[-1].value == 'err' and isinstance(items[-2], Expr.Symbol):
                    return Expr.Error(items[-2].value, origin=items[-3]), i + 1
                if len(items) == 2 and isinstance(items[-1], Expr.Symbol) and items[-1].value == 'err' and isinstance(items[-2], Expr.Symbol):
                    return Expr.Error(items[-2].value), i + 1
                return Expr.ListExpr(items), i + 1
            expr, i = _parse_one(tokens, i)
            items.append(expr)
        raise ParseError("expected ')'")

    if tok == ')':
        raise ParseError("unexpected ')'")

    # try integer → Byte
    try:
        n = int(tok)
        return Expr.Byte(n), pos + 1
    except ValueError:
        return Expr.Symbol(tok), pos + 1

def parse(tokens: List[str]) -> Tuple[Expr, List[str]]:
    """Parse tokens into an Expr and return (expr, remaining_tokens)."""
    expr, next_pos = _parse_one(tokens, 0)
    return expr, tokens[next_pos:]