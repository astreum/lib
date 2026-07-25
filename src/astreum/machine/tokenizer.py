from typing import List


def tokenize(source: str) -> List[str]:
    """Tokenize source code into a list of tokens.

    Handles:
        - Whitespace and line comments (starting with `;`)
        - S-expressions with parentheses
        - Strings in double quotes
        - Quote shorthand (`'expr` becomes `(quote expr)`)
        - S-expression comments (`;; expr` skips the following expression)

    Args:
        source: The source code string to tokenize.

    Returns:
        List[str]: A list of token strings.
    """
    tokens: List[str] = []
    cur: List[str] = []
    n = len(source)
    i = 0

    def flush_cur() -> None:
        """Append the current accumulated characters as a token and clear."""
        if cur:
            tokens.append("".join(cur))
            cur.clear()

    def skip_line_comment(idx: int) -> int:
        """Skip to the end of the line starting at idx.

        Args:
            idx: The starting position after the comment delimiter.

        Returns:
            int: The position of the newline or end of source.
        """
        while idx < n and source[idx] != "\n":
            idx += 1
        return idx

    def skip_ws_and_comments(idx: int) -> int:
        """Skip whitespace and comments, returning the next meaningful position.

        Args:
            idx: The starting position to check.

        Returns:
            int: The position of the next non-whitespace, non-comment character.
        """
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
        """Skip an entire expression (balanced parens or single token).

        Args:
            idx: The starting position to check.

        Returns:
            int: The position after the complete expression.
        """
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
                if ch == ";" and idx + 1 < n and source[idx + 1] == ";":
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
            if ch == ";" and idx + 1 < n and source[idx + 1] == ";":
                break
            idx += 1
        return idx

    while i < n:
        i = skip_ws_and_comments(i)
        if i >= n:
            break
        ch = source[i]
        if ch == ";" and i + 1 < n and source[i + 1] == ";":
            flush_cur()
            i = skip_expression(i + 2)
            continue
        if ch == '"':
            flush_cur()
            start = i
            i += 1
            while i < n and source[i] != '"':
                i += 1
            if i < n:
                i += 1
            tokens.append(source[start:i])
            continue
        if ch == "'":
            flush_cur()
            if i + 1 < n and source[i + 1] not in (" ", "\t", "\n", "\r", ")", '"', ";") and not (
                source[i + 1] == "#" and i + 2 < n and source[i + 2] == ";"
            ):
                tokens.append("(")
                tokens.append("'")
                i += 1
                if source[i] == "(":
                    end = skip_expression(i)
                    tokens.extend(tokenize(source[i:end]))
                    i = end
                else:
                    j = i
                    while j < n and not source[j].isspace() and source[j] not in ("(", ")", '"', ";"):
                        if source[j] == "#" and j + 1 < n and source[j + 1] == ";":
                            break
                        j += 1
                    tokens.append(source[i:j])
                    i = j
                tokens.append(")")
                continue
            tokens.append("'")
            i += 1
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
