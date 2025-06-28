from typing import List, Tuple
from ..node import Expr

class ParseError(Exception):
    pass

def parse(tokens: List[str]) -> Tuple[Expr, List[str]]:
    if not tokens:
        raise ParseError("Unexpected end of input")

    first_token, *rest = tokens

    if first_token == '(':
        if not rest:
            raise ParseError("Expected token after '('")

        list_items = []
        inner_tokens = rest

        while inner_tokens:
            if inner_tokens[0] == ')':
                return Expr.ListExpr(list_items), inner_tokens[1:]

            expr, inner_tokens = parse(inner_tokens)
            list_items.append(expr)

        raise ParseError("Expected closing ')'")

    elif first_token == ')':
        raise ParseError("Unexpected closing parenthesis")

    elif first_token.startswith('"') and first_token.endswith('"'):
        string_content = first_token[1:-1]
        return Expr.String(string_content), rest

    else:
        try:
            number = int(first_token)
            return Expr.Integer(number), rest
        except ValueError:
            return Expr.Symbol(first_token), rest
