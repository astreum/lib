from __future__ import annotations

from .link import Link, ZERO32
from .bytes_ import Bytes


NIL = Link(None, None)


def bytes_list_to_expr(items: list[bytes]) -> Expr:
    if not items:
        return NIL
    result: Expr = Bytes(items[-1])
    for value in reversed(items[:-1]):
        result = Link(Bytes(value), result)
    return result


def link_list_to_expr(items: list[bytes]) -> Expr:
    if not items:
        return NIL
    head = Link(head_hash=items[0], tail=NIL)
    current = head
    for value in items[1:]:
        new_link = Link(head_hash=value, tail=NIL)
        current.tail = new_link
        current = new_link
    return head


def resolve_list_exprs(node, expr: Expr) -> tuple[list[Expr], list[bytes]]:
    result: list[Expr] = []
    missed: list[bytes] = []
    current = expr
    while isinstance(current, Link):
        if current.head is None and current.head_hash is not None:
            if current.head_hash == ZERO32:
                current.head = NIL
                current.head_hash = None
            else:
                resolved = node.get_expr(current.head_hash)
                if resolved is not None:
                    current.head = resolved
                    current.head_hash = None
                else:
                    missed.append(current.head_hash)
        if current.head is not None:
            result.append(current.head)
        if current.tail is None and current.tail_hash is not None:
            if current.tail_hash == ZERO32:
                current.tail = NIL
                current.tail_hash = None
            else:
                resolved = node.get_expr(current.tail_hash)
                if resolved is not None:
                    current.tail = resolved
                    current.tail_hash = None
                else:
                    missed.append(current.tail_hash)
                    break
        current = current.tail
    if not isinstance(current, Link) and current is not None:
        result.append(current)
    return result, missed


def resolve_inner_exprs(node, expr: Expr) -> tuple[list[Expr], list[bytes]]:
    result: list[Expr] = []
    missed: list[bytes] = []

    def _walk(e: Expr) -> None:
        result.append(e)
        if not isinstance(e, Link):
            return
        if e.head is None and e.head_hash is not None:
            resolved = node.get_expr(e.head_hash)
            if resolved is not None:
                e.head = resolved
                e.head_hash = None
            else:
                missed.append(e.head_hash)
        if e.head is not None:
            _walk(e.head)
        if e.tail is None and e.tail_hash is not None:
            resolved = node.get_expr(e.tail_hash)
            if resolved is not None:
                e.tail = resolved
                e.tail_hash = None
            else:
                missed.append(e.tail_hash)
                return
        if e.tail is not None:
            _walk(e.tail)

    _walk(expr)
    return result, missed
