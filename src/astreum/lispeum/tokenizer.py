

# Tokenizer function
from typing import List

class ParseError(Exception):
    pass

def tokenize(input: str) -> List[str]:
    tokens = []
    current_token = ""
    in_string = False
    escape = False

    for char in input:
        if in_string:
            if escape:
                current_token += char
                escape = False
            elif char == '\\':
                escape = True
            elif char == '"':
                in_string = False
                tokens.append(f'"{current_token}"')
                current_token = ""
            else:
                current_token += char
        else:
            if char.isspace():
                if current_token:
                    tokens.append(current_token)
                    current_token = ""
            elif char == '(' or char == ')':
                if current_token:
                    tokens.append(current_token)
                    current_token = ""
                tokens.append(char)
            elif char == '"':
                if current_token:
                    tokens.append(current_token)
                    current_token = ""
                in_string = True
            else:
                current_token += char

    if in_string:
        raise ParseError("Unterminated string literal")

    if current_token:
        tokens.append(current_token)

    return tokens
