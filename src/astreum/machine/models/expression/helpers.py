from __future__ import annotations

from .expr import Expr, ZERO32, bytes_, link, NIL


def bytes_list_to_expr(items: list[bytes]) -> Expr:
    if not items:
        return NIL
    result: Expr = bytes_(items[-1])
    for value in reversed(items[:-1]):
        result = link(bytes_(value), result)
    return result


def link_list_to_expr(items: list[bytes]) -> Expr:
    if not items:
        return NIL
    head = Expr("link", head_hash=items[0], tail=NIL)
    current = head
    for value in items[1:]:
        new_link = Expr("link", head_hash=value, tail=NIL)
        current._tail = new_link
        current = new_link
    return head


def resolve_list_exprs(node, expr: Expr) -> tuple[list[Expr], list[bytes]]:
    result: list[Expr] = []
    missed: list[bytes] = []
    current = expr
    while current._tag == "link":
        if current._head is None and current._head_hash is not None:
            if current._head_hash == ZERO32:
                current._head = NIL
                current._head_hash = None
            else:
                resolved = node.get_expr(current._head_hash)
                if resolved is not None:
                    current._head = resolved
                    current._head_hash = None
                else:
                    missed.append(current._head_hash)
        if current._head is not None:
            result.append(current._head)
        if current._tail is None and current._tail_hash is not None:
            if current._tail_hash == ZERO32:
                current._tail = NIL
                current._tail_hash = None
            else:
                resolved = node.get_expr(current._tail_hash)
                if resolved is not None:
                    current._tail = resolved
                    current._tail_hash = None
                else:
                    missed.append(current._tail_hash)
                    break
        current = current._tail
    if current is not None and current is not NIL:
        result.append(current._head if current._tag == "link" else current)
    return result, missed


def resolve_inner_exprs(node, expr: Expr) -> tuple[list[Expr], list[bytes]]:
    result: list[Expr] = []
    missed: list[bytes] = []

    def _walk(e: Expr) -> None:
        result.append(e)
        if e._tag != "link":
            return
        if e._head is None and e._head_hash is not None:
            resolved = node.get_expr(e._head_hash)
            if resolved is not None:
                e._head = resolved
                e._head_hash = None
            else:
                missed.append(e._head_hash)
        if e._head is not None:
            _walk(e._head)
        if e._tail is None and e._tail_hash is not None:
            resolved = node.get_expr(e._tail_hash)
            if resolved is not None:
                e._tail = resolved
                e._tail_hash = None
            else:
                missed.append(e._tail_hash)
                return
        if e._tail is not None:
            _walk(e._tail)

    _walk(expr)
    return result, missed
