from typing import List


def tokenize(source: str) -> List[str]:
    tokens: List[str] = []
    cur: List[str] = []
    for ch in source:
        if ch.isspace():
            if cur:
                tokens.append("".join(cur))
                cur = []
            continue
        if ch in ("(", ")"):
            if cur:
                tokens.append("".join(cur))
                cur = []
            tokens.append(ch)
            continue
        cur.append(ch)
    if cur:
        tokens.append("".join(cur))
    return tokens