from typing import List, Tuple
from astreum.machine.models.expression import Expr, NIL, int_, fp64_, bytes_, str_, symbol, link

class ParseError(Exception):
    pass


def _build_chain(items: List[Expr]) -> Expr:
    """Build a right-linked Link chain from parsed items, nil-terminated.

    ()       → NIL
    (x)      → Link(x, NIL)
    (a b c)  → Link(a, Link(b, Link(c, NIL)))
    """
    result: Expr = NIL
    for item in reversed(items):
        result = link(item, result)
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
        return str_(content), pos + 1

    if tok[:2].lower() == "0x":
        return bytes_(bytes.fromhex(tok[2:])), pos + 1

    try:
        return int_(int(tok)), pos + 1
    except ValueError:
        pass

    if "." in tok:
        try:
            return fp64_(float(tok)), pos + 1
        except ValueError:
            pass

    return symbol(tok), pos + 1

def parse(tokens: List[str]) -> Tuple[Expr, List[str]]:
    """Parse tokens into an Expr and return (expr, remaining_tokens)."""
    expr, next_pos = _parse_one(tokens, 0)
    return expr, tokens[next_pos:]
