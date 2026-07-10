from typing import List, Tuple
from astreum.expression import Expr, NIL, int_, fp64_, bytes_, str_, symbol, link

class ParseError(Exception):
    pass


def _build_chain(items: List[Expr]) -> Expr:
    """Build a right-linked Link chain from parsed items, nil-terminated.

    ()       → '( )  (so it evaluates to NIL when run)
    (x)      → Link(x, NIL)
    (a b c)  → Link(a, Link(b, Link(c, NIL)))

    Args:
        items: A list of Expr objects to chain together.

    Returns:
        Expr: A Link chain terminating in NIL, or NIL if items is empty.
    """
    if not items:
        return link(symbol("'"), NIL)
    result: Expr = NIL
    for item in reversed(items):
        result = link(item, result)
    return result


def _parse_one(tokens: List[str], pos: int = 0) -> Tuple[Expr, int]:
    """Parse a single expression starting at the given position.

    Args:
        tokens: The list of tokens to parse.
        pos: The starting position in the token list. Defaults to 0.

    Returns:
        Tuple[Expr, int]: A tuple containing the parsed Expr and the position
            of the next token after the parsed expression.

    Raises:
        ParseError: If there is an unexpected end of input, an unexpected
            closing parenthesis, or a malformed token.
    """
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
    """Parse tokens into an Expr and return (expr, remaining_tokens).

    Args:
        tokens: The list of tokens to parse.

    Returns:
        Tuple[Expr, List[str]]: A tuple containing the parsed Expr and the
            list of remaining unparsed tokens.
    """
    expr, next_pos = _parse_one(tokens, 0)
    return expr, tokens[next_pos:]
