from typing import List, Tuple
from . import Expr

class ParseError(Exception):
    pass


def _build_chain(items: List[Expr]) -> Expr:
    """Build a right-linked Link chain from parsed items.

    ()       → Link(None, None)   (NIL)
    (x)      → Link(x, None)
    (a b c)  → Link(a, Link(b, c))
    """
    if not items:
        return Expr.Link(None, None)
    if len(items) == 1:
        return Expr.Link(items[0], None)
    result = items[-1]
    for item in reversed(items[:-1]):
        result = Expr.Link(item, result)
    return result


def _parse_one(tokens: List[str], pos: int = 0) -> Tuple[Expr, int]:
    if pos >= len(tokens):
        raise ParseError("unexpected end")
    tok = tokens[pos]

    if tok == '(':  # link chain
        items: List[Expr] = []
        i = pos + 1
        while i < len(tokens):
            if tokens[i] == ')':
                return _build_chain(items), i + 1
            expr, i = _parse_one(tokens, i)
            items.append(expr)
        raise ParseError("expected ')'")

    if tok == ')':
        raise ParseError("unexpected ')'")

    if tok.startswith('"'):
        content = tok[1:-1] if len(tok) >= 2 and tok[-1] == '"' else tok[1:]
        return Expr.String(content), pos + 1

    if tok[:2].lower() == "0x":
        return Expr.Bytes(bytes.fromhex(tok[2:])), pos + 1

    try:
        return Expr.Int(int(tok)), pos + 1
    except ValueError:
        pass

    if "." in tok:
        try:
            return Expr.Float(float(tok)), pos + 1
        except ValueError:
            pass

    return Expr.Symbol(tok), pos + 1

def parse(tokens: List[str]) -> Tuple[Expr, List[str]]:
    """Parse tokens into an Expr and return (expr, remaining_tokens)."""
    expr, next_pos = _parse_one(tokens, 0)
    return expr, tokens[next_pos:]
