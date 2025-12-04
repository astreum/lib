from typing import List


def tokenize(source: str) -> List[str]:
    tokens: List[str] = []
    cur: List[str] = []
    n = len(source)
    i = 0

    def flush_cur() -> None:
        if cur:
            tokens.append("".join(cur))
            cur.clear()

    def skip_line_comment(idx: int) -> int:
        while idx < n and source[idx] != "\n":
            idx += 1
        return idx

    def skip_ws_and_comments(idx: int) -> int:
        while idx < n:
            ch = source[idx]
            if ch.isspace():
                flush_cur()
                idx += 1
                continue
            if ch == ";":
                flush_cur()
                idx = skip_line_comment(idx + 1)
                continue
            break
        return idx

    def skip_expression(idx: int) -> int:
        idx = skip_ws_and_comments(idx)
        if idx >= n:
            return n
        ch = source[idx]
        if ch == "(":
            depth = 0
            while idx < n:
                ch = source[idx]
                if ch == "(":
                    depth += 1
                    idx += 1
                    continue
                if ch == ")":
                    depth -= 1
                    idx += 1
                    if depth == 0:
                        break
                    continue
                if ch == ";":
                    idx = skip_line_comment(idx + 1)
                    continue
                if ch == "#" and idx + 1 < n and source[idx + 1] == ";":
                    idx = skip_expression(idx + 2)
                    continue
                idx += 1
            return idx
        if ch == ")":
            return idx + 1
        while idx < n:
            ch = source[idx]
            if ch.isspace() or ch in ("(", ")", ";"):
                break
            if ch == "#" and idx + 1 < n and source[idx + 1] == ";":
                break
            idx += 1
        return idx

    while i < n:
        i = skip_ws_and_comments(i)
        if i >= n:
            break
        ch = source[i]
        if ch == "#" and i + 1 < n and source[i + 1] == ";":
            flush_cur()
            i = skip_expression(i + 2)
            continue
        if ch in ("(", ")"):
            flush_cur()
            tokens.append(ch)
            i += 1
            continue
        cur.append(ch)
        i += 1

    flush_cur()
    return tokens
